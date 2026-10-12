"""
corrigir_pipeline_reprocessar.py
--------------------------------
Corrige o SQLite com base nos JSONs originais.

O que faz:
  1. Faz backup do ispaam.db (ispaam.db.bak_YYYYMMDD_HHMMSS)
  2. Lê cada JSON (fonte primária)
  3. Para cada registro em 09:00 e 15:00:
       - tmin/tmin_real: se JSON tem NULL -> SQLite vira NULL
                         se JSON tem valor -> SQLite recebe valor
       - tmax/tmax_real: idem
       - tmed: recalcula. Se tmin ou tmax são NULL -> tmed vira NULL.
       - tar: idem (não deve mudar, mas garante consistência)
  4. Reporta quantos registros foram alterados por ano

Uso:
  python corrigir_pipeline_reprocessar.py            # dry-run (padrão)
  python corrigir_pipeline_reprocessar.py --aplicar  # executa

IMPORTANTE: sempre rodar em dry-run primeiro.
"""

import csv
import json
import shutil
import sqlite3
import sys
from pathlib import Path
from datetime import datetime

# ---------------------------------------------------------------------------
# Configuração — CAMINHOS ABSOLUTOS
# ---------------------------------------------------------------------------
BASE_PROJETO = Path(r"C:\Users\luizt\Desktop\ISPAAM API\agromet-ufra")
DIR_JSON     = BASE_PROJETO / "dados_brutos"
DB_PATH      = BASE_PROJETO / "banco" / "ispaam.db"

PADRAO_JSON = "dados_{ano}.json"
ANOS = list(range(2018, 2027))

SAIDA_LOG = DIR_JSON / "correcao_pipeline_log.csv"

APLICAR = "--aplicar" in sys.argv

# Faixas de plausibilidade
FAIXA_TMIN = (15.0, 27.0)
FAIXA_TMAX = (25.0, 40.0)
FAIXA_TAR  = (15.0, 40.0)


# ---------------------------------------------------------------------------
# Utilidades (idênticas às do diagnóstico)
# ---------------------------------------------------------------------------
def para_float(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not s or s.lower() == "null" or s == "-" or s == "--" or s.startswith("#"):
        return None
    try:
        return float(s.replace(",", "."))
    except ValueError:
        return None


def normalizar_data(data_str, ano):
    if not data_str:
        return None
    s = str(data_str).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    try:
        dt = datetime.strptime(s, "%d/%m")
        return dt.replace(year=ano).strftime("%Y-%m-%d")
    except ValueError:
        return None


def normalizar_hora(hora_str):
    if not hora_str:
        return None
    s = str(hora_str).strip()
    try:
        h, m = s.split(":")
        return f"{int(h):02d}:{int(m):02d}"
    except (ValueError, AttributeError):
        return None


def dentro_faixa(v, faixa):
    return v is not None and faixa[0] <= v <= faixa[1]


# ---------------------------------------------------------------------------
# Carregar JSON
# ---------------------------------------------------------------------------
def carregar_json_ano(caminho, ano):
    with open(caminho, encoding="utf-8") as f:
        dados = json.load(f)

    registros = []
    for r in dados:
        data_iso = normalizar_data(r.get("Data    (dd/mm/aaaa)"), ano)
        hora = normalizar_hora(r.get("Hora local (hh:mm)"))
        if not data_iso or not hora:
            continue

        tmax = para_float(r.get("Tmáx (°C)"))
        tmin = para_float(r.get("Tmin (°C)"))
        tmax_real = para_float(r.get("Tmáx Real (ºC)"))
        tmin_real = para_float(r.get("Tmin Real (ºC)"))
        tar = para_float(r.get("Tar (°C)"))
        tar2 = para_float(r.get("Tar 2 (°C)"))
        tmed_raw = para_float(r.get("Tméd (ºC)"))

        # Aplicar faixas: valores fora da faixa viram NULL
        if not dentro_faixa(tmin, FAIXA_TMIN):
            tmin = None
        if not dentro_faixa(tmax, FAIXA_TMAX):
            tmax = None
        if not dentro_faixa(tmin_real, FAIXA_TMIN):
            tmin_real = None
        if not dentro_faixa(tmax_real, FAIXA_TMAX):
            tmax_real = None
        if not dentro_faixa(tar, FAIXA_TAR):
            tar = None
        if not dentro_faixa(tar2, FAIXA_TAR):
            tar2 = None

        # Recalcular tmed corretamente:
        #   Prioridade: tmin_real/tmax_real > tmin/tmax
        tmin_base = tmin_real if tmin_real is not None else tmin
        tmax_base = tmax_real if tmax_real is not None else tmax

        if tmin_base is not None and tmax_base is not None:
            tmed = (tmin_base + tmax_base) / 2
        else:
            tmed = None

        registros.append({
            "data_iso": data_iso,
            "hora_local": hora,
            "tar": tar,
            "tar2": tar2,
            "tmax": tmax,
            "tmin": tmin,
            "tmax_real": tmax_real,
            "tmin_real": tmin_real,
            "tmed": tmed,
        })
    return registros


# ---------------------------------------------------------------------------
# Corrigir SQLite
# ---------------------------------------------------------------------------
def corrigir_sqlite(caminho_db, aplicar=False):
    con = sqlite3.connect(caminho_db)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    cur.execute("PRAGMA table_info(observacoes)")
    cols = {r[1] for r in cur.fetchall()}

    def pick(*nomes):
        for n in nomes:
            if n in cols:
                return n
        return None

    c_tar       = pick("tar")
    c_tar2      = pick("tar2", "tar_2")
    c_tmax      = pick("tmax_real", "tmax")
    c_tmin      = pick("tmin_real", "tmin")
    c_tmax_real = pick("tmax_real")
    c_tmin_real = pick("tmin_real")
    c_tmed      = pick("tmed")

    if not (c_tmin and c_tmax):
        print("ERRO: colunas tmin/tmax não encontradas")
        con.close()
        return []

    # Coleta todos os registros primeiro
    sql = f"""
        SELECT data_iso, hora_local
        FROM observacoes
        WHERE hora_local IN ('09:00', '15:00')
    """
    chaves = [(r["data_iso"], r["hora_local"]) for r in cur.execute(sql)]
    print(f"      {len(chaves)} registros em 09:00/15:00")

    # Monta SET/WHERE por registro
    log = []
    n_atualizados = 0

    for ano in ANOS:
        caminho = DIR_JSON / PADRAO_JSON.format(ano=ano)

        if not caminho.exists():
            continue

        try:
            json_regs = carregar_json_ano(caminho, ano)
        except Exception as e:
            print(f"      {ano}: erro — {e}")
            continue

        for jr in json_regs:
            chave = (jr["data_iso"], jr["hora_local"])
            if chave not in chaves:
                continue

            # Monta UPDATE só com os campos que existem na tabela
            campos = []
            valores = []

            if c_tmin and jr["tmin"] != "SKIP":
                campos.append(f"{c_tmin} = ?")
                valores.append(jr["tmin"])
            if c_tmax and jr["tmax"] != "SKIP":
                campos.append(f"{c_tmax} = ?")
                valores.append(jr["tmax"])
            if c_tmax_real and jr["tmax_real"] != "SKIP":
                campos.append(f"{c_tmax_real} = ?")
                valores.append(jr["tmax_real"])
            if c_tmin_real and jr["tmin_real"] != "SKIP":
                campos.append(f"{c_tmin_real} = ?")
                valores.append(jr["tmin_real"])
            if c_tar and jr["tar"] != "SKIP":
                campos.append(f"{c_tar} = ?")
                valores.append(jr["tar"])
            if c_tar2 and jr["tar2"] != "SKIP":
                campos.append(f"{c_tar2} = ?")
                valores.append(jr["tar2"])
            if c_tmed and jr["tmed"] != "SKIP":
                campos.append(f"{c_tmed} = ?")
                valores.append(jr["tmed"])

            if not campos:
                continue

            valores.extend([jr["data_iso"], jr["hora_local"]])
            sql_update = f"""
                UPDATE observacoes
                SET {', '.join(campos)}
                WHERE data_iso = ? AND hora_local = ?
            """

            if aplicar:
                try:
                    cur.execute(sql_update, valores)
                    n_atualizados += 1
                except Exception as e:
                    log.append({
                        "ano": ano, "data": jr["data_iso"], "hora": jr["hora_local"],
                        "erro": str(e),
                    })

            log.append({
                "ano": ano,
                "data": jr["data_iso"],
                "hora": jr["hora_local"],
                "json_tmin": jr["tmin"],
                "json_tmax": jr["tmax"],
                "json_tmed": jr["tmed"],
                "aplicado": aplicar,
            })

    if aplicar:
        con.commit()
        print(f"      {n_atualizados} registros atualizados")

    con.close()
    return log


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    modo = "APLICAR" if APLICAR else "DRY-RUN (não altera nada)"
    print("=" * 78)
    print(f" CORREÇÃO DO PIPELINE — modo: {modo}")
    print("=" * 78)

    if not APLICAR:
        print("\n  >> Modo dry-run. Nada será alterado.")
        print("  >> Para aplicar, rode com --aplicar\n")
    else:
        # Backup
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = DB_PATH.with_suffix(f".db.bak_{ts}")
        print(f"\n[1/2] Fazendo backup: {backup.name}")
        shutil.copy2(DB_PATH, backup)
        print(f"      Backup criado com sucesso")

    print(f"[2/2] Corrigindo SQLite a partir dos JSONs...")
    log = corrigir_sqlite(DB_PATH, aplicar=APLICAR)

    # Exporta log
    with open(SAIDA_LOG, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "ano", "data", "hora",
            "json_tmin", "json_tmax", "json_tmed",
            "aplicado", "erro",
        ])
        w.writeheader()
        for item in log:
            item.setdefault("erro", "")
            w.writerow(item)

    print(f"\n  Log exportado: {SAIDA_LOG}")

    if not APLICAR:
        print("\n" + "=" * 78)
        print(" PRÓXIMO PASSO")
        print("=" * 78)
        print("  1. Abra o CSV e confira se os valores do JSON parecem corretos")
        print("  2. Se estiver tudo bem, rode novamente com --aplicar")
        print("  3. Verifique se o backup foi criado")
    else:
        print("\n" + "=" * 78)
        print(" CORREÇÃO APLICADA")
        print("=" * 78)
        print("  Backup salvo. SQLite reprocessado.")
        print("  Rode o script de diagnóstico de novo para confirmar")


if __name__ == "__main__":
    main()