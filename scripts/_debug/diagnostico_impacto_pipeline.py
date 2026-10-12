"""
diagnostico_impacto_pipeline.py
-------------------------------
Varre os JSON de 2018-2026 e reporta o que será corrigido no SQLite.

NÃO ALTERA NADA. Apenas lê e reporta.

Para cada registro com hora_local = 09:00 e 15:00:
  - Lê tmin, tmax, tmin_real, tmax_real, tmed, tar do JSON
  - Compara com o SQLite atual
  - Identifica casos onde o pipeline corrompeu o dado:
      * SQLite tem tmin = tmax, mas JSON tem tmin = null
      * SQLite tem tmed absurdo (16-18), mas JSON calcula corretamente
  - Estima quantos registros serão afetados pela correção

Saída:
  - diagnostico_pipeline_YYYY.csv (por ano)
  - diagnostico_pipeline_resumo.csv
"""

import csv
import json
import sqlite3
from pathlib import Path
from datetime import datetime

# ---------------------------------------------------------------------------
# Configuração — CAMINHOS ABSOLUTOS
# ---------------------------------------------------------------------------
BASE_PROJETO = Path(r"C:\Users\luizt\Desktop\ISPAAM API\agromet-ufra")
DIR_JSON     = BASE_PROJETO / "dados_brutos"
DB_PATH      = BASE_PROJETO / "banco" / "ispaam.db"

PADRAO_JSON = "dados_{ano}.json"

SAIDA_RESUMO  = DIR_JSON / "diagnostico_pipeline_resumo.csv"
SAIDA_DETALHE = DIR_JSON / "diagnostico_pipeline_detalhe.csv"

ANOS = list(range(2018, 2027))

# Faixas plausíveis (para detectar valores absurdos)
FAIXA_TMED = (18.0, 40.0)   # Tméd real é 25-32 °C em Belém; 16-18 é absurdo
FAIXA_TMIN = (15.0, 27.0)
FAIXA_TMAX = (25.0, 40.0)
FAIXA_TAR  = (15.0, 40.0)


# ---------------------------------------------------------------------------
# Utilidades
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
    """
    JSON pode ter 'DD/MM' (sem ano) ou 'DD/MM/YYYY'.
    Se for só 'DD/MM', usa o ano do arquivo.
    Retorna ISO 'YYYY-MM-DD' ou None.
    """
    if not data_str:
        return None
    s = str(data_str).strip()
    # Tenta DD/MM/YYYY
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    # Tenta DD/MM (sem ano)
    try:
        dt = datetime.strptime(s, "%d/%m")
        return dt.replace(year=ano).strftime("%Y-%m-%d")
    except ValueError:
        return None


def normalizar_hora(hora_str):
    """'09:00' -> '09:00'; '9:00' -> '09:00'; retorna None se inválido."""
    if not hora_str:
        return None
    s = str(hora_str).strip()
    try:
        h, m = s.split(":")
        return f"{int(h):02d}:{int(m):02d}"
    except (ValueError, AttributeError):
        return None


# ---------------------------------------------------------------------------
# Carregar JSON
# ---------------------------------------------------------------------------
def carregar_json_ano(caminho, ano):
    """Retorna lista de dicts com campos normalizados."""
    with open(caminho, encoding="utf-8") as f:
        dados = json.load(f)

    registros = []
    for r in dados:
        data_iso = normalizar_data(r.get("Data    (dd/mm/aaaa)"), ano)
        hora = normalizar_hora(r.get("Hora local (hh:mm)"))
        if not data_iso or not hora:
            continue

        registros.append({
            "data_iso": data_iso,
            "hora_local": hora,
            "tar":       para_float(r.get("Tar (°C)")),
            "tar2":      para_float(r.get("Tar 2 (°C)")),
            "tmax":      para_float(r.get("Tmáx (°C)")),
            "tmin":      para_float(r.get("Tmin (°C)")),
            "tmax_real": para_float(r.get("Tmáx Real (ºC)")),
            "tmin_real": para_float(r.get("Tmin Real (ºC)")),
            "tmed":      para_float(r.get("Tméd (ºC)")),
        })
    return registros


# ---------------------------------------------------------------------------
# Carregar SQLite
# ---------------------------------------------------------------------------
def carregar_sqlite(caminho_db):
    con = sqlite3.connect(caminho_db)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    # Descobre colunas disponíveis
    cur.execute("PRAGMA table_info(observacoes)")
    cols = {r[1] for r in cur.fetchall()}

    # Colunas alvo (com fallback)
    def pick(*nomes):
        for n in nomes:
            if n in cols:
                return n
        return None

    c_tar    = pick("tar")
    c_tmax   = pick("tmax_real", "tmax")
    c_tmin   = pick("tmin_real", "tmin")
    c_tmed   = pick("tmed")
    c_prp    = pick("prp")
    c_ev     = pick("ev_mm_dia", "ev_mm")

    sql = f"""
        SELECT data_iso, hora_local,
               {c_tar} AS tar,
               {c_tmax} AS tmax,
               {c_tmin} AS tmin,
               {c_tmed} AS tmed
        FROM observacoes
        WHERE hora_local IN ('09:00', '15:00')
    """
    registros = {}
    for row in cur.execute(sql):
        chave = (row["data_iso"], row["hora_local"])
        registros[chave] = dict(row)
    con.close()
    return registros


# ---------------------------------------------------------------------------
# Comparar e reportar
# ---------------------------------------------------------------------------
def classificar_diferenca(json_rec, sqlite_rec):
    """
    Retorna:
      - categoria: string descrevendo o problema
      - precisa_corrigir: bool
      - novo_valor: valor correto (do JSON)
    """
    if sqlite_rec is None:
        return ("ausente_no_sqlite", False, None)

    j_tmin  = json_rec["tmin"]
    j_tmax  = json_rec["tmax"]
    j_tmed  = json_rec["tmed"]
    j_tar   = json_rec["tar"]

    s_tmin  = sqlite_rec["tmin"]
    s_tmax  = sqlite_rec["tmax"]
    s_tmed  = sqlite_rec["tmed"]

    # Caso 1 — JSON tem tmin NULL, mas SQLite tem valor
    #          (provável fallback Tmin := Tmáx)
    if j_tmin is None and s_tmin is not None:
        # Confirma se é igual a tmax (fallback clássico)
        if s_tmin == s_tmax and j_tmax is not None and abs(s_tmin - j_tmax) < 0.01:
            return ("tmin_fallback_de_tmax", True, None)
        return ("tmin_null_no_json_mas_sqlite_tem", True, None)

    # Caso 2 — Tméd absurda no SQLite (16-18 °C), mas JSON também
    if s_tmed is not None and not (FAIXA_TMED[0] <= s_tmed <= FAIXA_TMED[1]):
        # Se o JSON tem tmed calculável corretamente
        if j_tmin is not None and j_tmax is not None:
            tmed_correto = (j_tmin + j_tmax) / 2
            return ("tmed_absurda", True, tmed_correto)
        else:
            # JSON também não tem como calcular — deve virar NULL
            return ("tmed_absurda_sem_dados", True, None)

    return (None, False, None)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 78)
    print(" DIAGNÓSTICO DE IMPACTO DO PIPELINE")
    print(" (não altera nada — apenas reporta)")
    print("=" * 78)

    print(f"\n[1/2] Carregando SQLite...")
    sqlite_regs = carregar_sqlite(DB_PATH)
    print(f"      {len(sqlite_regs)} registros em 09:00/15:00")

    resumo = []
    detalhe = []

    print(f"[2/2] Analisando JSONs de {ANOS[0]} a {ANOS[-1]}...")

    for ano in ANOS:
        caminho = DIR_JSON / PADRAO_JSON.format(ano=ano)
        if not caminho.exists():
            print(f"      {ano}: JSON não encontrado em {caminho}")
            continue

        try:
            json_regs = carregar_json_ano(caminho, ano)
        except Exception as e:
            print(f"      {ano}: erro ao ler JSON — {e}")
            continue

        n_totais = len(json_regs)
        n_tmin_fallback = 0
        n_tmin_null = 0
        n_tmed_absurda = 0
        n_ok = 0

        for jr in json_regs:
            chave = (jr["data_iso"], jr["hora_local"])
            sr = sqlite_regs.get(chave)

            cat, precisa, novo = classificar_diferenca(jr, sr)

            if cat is None:
                n_ok += 1
                continue

            if cat == "tmin_fallback_de_tmax":
                n_tmin_fallback += 1
            elif cat == "tmin_null_no_json_mas_sqlite_tem":
                n_tmin_null += 1
            elif cat.startswith("tmed_absurda"):
                n_tmed_absurda += 1

            detalhe.append({
                "ano": ano,
                "data": jr["data_iso"],
                "hora": jr["hora_local"],
                "categoria": cat,
                "json_tmin": jr["tmin"],
                "json_tmax": jr["tmax"],
                "json_tmed": jr["tmed"],
                "sqlite_tmin": sr["tmin"] if sr else None,
                "sqlite_tmax": sr["tmax"] if sr else None,
                "sqlite_tmed": sr["tmed"] if sr else None,
                "acao": "anular" if novo is None else f"corrigir para {novo:.2f}",
            })

        pct_fb  = 100 * n_tmin_fallback / n_totais if n_totais else 0
        pct_med = 100 * n_tmed_absurda / n_totais if n_totais else 0

        print(f"\n {ano} ({n_totais} registros)")
        print(f"   OK:                          {n_ok:5d}")
        print(f"   tmin fallback de tmax:       {n_tmin_fallback:5d}  ({pct_fb:.1f}%)")
        print(f"   tmin null no JSON, SQLite tem: {n_tmin_null:5d}")
        print(f"   tmed absurda (16-18 °C):     {n_tmed_absurda:5d}  ({pct_med:.1f}%)")

        resumo.append({
            "ano": ano,
            "n_registros": n_totais,
            "ok": n_ok,
            "tmin_fallback": n_tmin_fallback,
            "tmin_null_sqlite_tem": n_tmin_null,
            "tmed_absurda": n_tmed_absurda,
        })

    # Exportar
    print("\n" + "=" * 78)
    print(" EXPORTANDO")
    print("=" * 78)

    with open(SAIDA_RESUMO, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "ano", "n_registros", "ok",
            "tmin_fallback", "tmin_null_sqlite_tem", "tmed_absurda"
        ])
        w.writeheader()
        w.writerows(resumo)
    print(f"  {SAIDA_RESUMO}")

    with open(SAIDA_DETALHE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "ano", "data", "hora", "categoria",
            "json_tmin", "json_tmax", "json_tmed",
            "sqlite_tmin", "sqlite_tmax", "sqlite_tmed",
            "acao",
        ])
        w.writeheader()
        w.writerows(detalhe)
    print(f"  {SAIDA_DETALHE}")

    # Síntese
    total_fb = sum(r["tmin_fallback"] for r in resumo)
    total_med = sum(r["tmed_absurda"] for r in resumo)
    total_ok = sum(r["ok"] for r in resumo)
    print("\n" + "=" * 78)
    print(" SÍNTESE")
    print("=" * 78)
    print(f"  Registros OK:                    {total_ok}")
    print(f"  Registros com tmin corrompido:   {total_fb}")
    print(f"  Registros com tmed absurda:      {total_med}")
    print()
    print("  >> Esses são os registros que a correção vai limpar.")
    print("  >> Rode o script de correção (parte 2) depois de conferir.")


if __name__ == "__main__":
    main()