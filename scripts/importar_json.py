"""
importar_json.py
----------------
Lê os arquivos dados_YYYY.json de dados_brutos/ e insere no banco ispaam.db.

Regras:
- O ano é extraído do nome do arquivo (dados_2026.json -> 2026).
- "Data (dd/mm/aaaa)" contém dd/mm; o ano vem do nome do arquivo.
- "" é convertido para NULL no banco.
- Números em formato "33,60" viram 33.60 (float).
- A coluna "protocolo" é preenchida com base na hora local.

Uso:
    python scripts/importar_json.py
    python scripts/importar_json.py dados_brutos/dados_2026.json
"""

import json
import re
import sqlite3
import sys
import argparse
from pathlib import Path
from datetime import datetime


CAMINHO_BANCO  = Path("banco/ispaam.db")
PASTA_BRUTOS   = Path("dados_brutos")
PADRAO_ARQUIVO = re.compile(r"^dados_(\d{4})\.json$")
CODIGO_ESTACAO = "UFRA-BEL"

PROTOCOLO_POR_HORA = {
    "09:00": "completo",
    "15:00": "reduzido",
}

MAPA_CAMPOS = {
    "Tar (°C)":              "tar",
    "TH2O ev (°C)":          "th2o_ev",
    "Tmáx (°C)":             "tmax",
    "Tmin (°C)":             "tmin",
    "Tmáx Real (ºC)":        "tmax_real",
    "Tmin Real (ºC)":        "tmin_real",
    "Tméd (ºC)":             "tmed",
    "UR (%)":                "ur",
    "esTU":                  "estu",
    "ea":                    "ea",
    "es":                    "es",
    "Direção do vento":      "direcao_vento",
    "U2 (m/s)":              "u2",
    "Prp (mm/dia)":          "prp",
    "Soma de Prp (mm/dia)":  "soma_prp",
    "pluv. alternativo (ml)":"pluv_alt",
    "Ev (mm)":               "ev_mm",
    "Ev (mm)*":              "ev_mm_ast",
    "Ev (mm/dia)":           "ev_mm_dia",
    "Tanque":                "tanque",
    "Patm (mbar)":           "patm",
    "Evento":                "evento",
    "Visibilidade":          "visibilidade",
    "Nuvem":                 "nuvem",
    "Cobertura do céu":      "cobertura_ceu",
    "Observadores":          "observadores",
}


def para_float(valor):
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    if isinstance(valor, str):
        s = valor.strip().replace(",", ".")
        if not s:
            return None
        try:
            return float(s)
        except ValueError:
            return None
    return None


def limpar_texto(valor):
    if valor is None:
        return None
    if isinstance(valor, str):
        s = valor.strip()
        return s if s else None
    return str(valor)


def montar_data_iso(data_dd_mm, ano):
    if not data_dd_mm:
        return None
    partes = str(data_dd_mm).split("/")
    try:
        if len(partes) == 3:
            dia, mes, a = int(partes[0]), int(partes[1]), int(partes[2])
            return f"{a:04d}-{mes:02d}-{dia:02d}"
        elif len(partes) == 2:
            dia, mes = int(partes[0]), int(partes[1])
            return f"{ano:04d}-{mes:02d}-{dia:02d}"
    except (ValueError, IndexError):
        pass
    return None


def extrair_ano(nome_arquivo):
    m = PADRAO_ARQUIVO.match(nome_arquivo)
    return int(m.group(1)) if m else None


def importar_arquivo(caminho: Path):
    ano = extrair_ano(caminho.name)
    if ano is None:
        print(f"  [SKIP] {caminho.name}: nome não segue o padrão dados_YYYY.json")
        return 0

    with open(caminho, encoding="utf-8") as f:
        linhas = json.load(f)

    con = sqlite3.connect(CAMINHO_BANCO)
    con.execute("PRAGMA foreign_keys = ON;")
    cur = con.cursor()

    cur.execute("SELECT id FROM estacoes WHERE codigo = ?", (CODIGO_ESTACAO,))
    row = cur.fetchone()
    if not row:
        print(f"  [ERRO] Estação '{CODIGO_ESTACAO}' não existe no banco.")
        print(f"         Rode scripts/criar_banco.py primeiro.")
        con.close()
        sys.exit(1)
    estacao_id = row[0]

    cur.execute(
        """
        INSERT INTO importacoes (arquivo, estacao_codigo, importado_em, total_registros, observacoes)
        VALUES (?, ?, ?, ?, ?)
        """,
        (caminho.name, CODIGO_ESTACAO,
         datetime.now().isoformat(timespec="seconds"),
         len(linhas), f"Importação de {caminho.name}"),
    )
    importacao_id = cur.lastrowid

    inseridos = 0
    ignorados = 0
    erros = 0

    for linha in linhas:
        data_raw = linha.get("Data    (dd/mm/aaaa)")
        hora = limpar_texto(linha.get("Hora local (hh:mm)"))
        data_iso = montar_data_iso(data_raw, ano)

        if not data_iso or not hora:
            ignorados += 1
            continue

        protocolo = PROTOCOLO_POR_HORA.get(hora)

        valores = {
            "estacao_id":    estacao_id,
            "importacao_id": importacao_id,
            "data_iso":      data_iso,
            "hora_local":    hora,
            "hora_utc":      limpar_texto(linha.get("Hora UTC (hh:mm)")),
            "dia_semana":    limpar_texto(linha.get("  ")),
            "protocolo":     protocolo,
        }

        for chave_json, coluna_db in MAPA_CAMPOS.items():
            raw = linha.get(chave_json)
            if coluna_db in ("direcao_vento", "evento", "visibilidade",
                             "nuvem", "cobertura_ceu", "observadores"):
                valores[coluna_db] = limpar_texto(raw)
            else:
                valores[coluna_db] = para_float(raw)

        colunas      = ", ".join(valores.keys())
        placeholders = ", ".join(f":{k}" for k in valores.keys())
        sql = f"INSERT OR REPLACE INTO observacoes ({colunas}) VALUES ({placeholders})"

        try:
            cur.execute(sql, valores)
            inseridos += 1
        except sqlite3.Error as e:
            erros += 1
            print(f"    [ERRO] {data_iso} {hora}: {e}")

    cur.execute(
        "UPDATE importacoes SET total_registros = ? WHERE id = ?",
        (inseridos, importacao_id),
    )

    con.commit()
    con.close()

    print(f"  {caminho.name} (ano {ano}):")
    print(f"    Inseridos:  {inseridos}")
    if ignorados:
        print(f"    Ignorados:  {ignorados} (sem data/hora válida)")
    if erros:
        print(f"    Erros:      {erros}")

    return inseridos


def main():
    if not CAMINHO_BANCO.exists():
        print(f"Banco não encontrado: {CAMINHO_BANCO}")
        print("Rode 'python scripts/criar_banco.py' primeiro.")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Importa JSONs para o banco ispaam.db.")
    parser.add_argument("arquivo", nargs="?",
                        help="Arquivo específico. Se omitido, importa todos os dados_*.json de dados_brutos/.")
    args = parser.parse_args()

    if args.arquivo:
        caminho = Path(args.arquivo)
        if not caminho.exists():
            print(f"Arquivo não encontrado: {caminho}")
            sys.exit(1)
        arquivos = [caminho]
    else:
        arquivos = sorted(
            p for p in PASTA_BRUTOS.iterdir()
            if p.is_file() and PADRAO_ARQUIVO.match(p.name)
        )

    if not arquivos:
        print(f"Nenhum arquivo dados_YYYY.json encontrado em {PASTA_BRUTOS}/")
        sys.exit(1)

    print(f"Importando {len(arquivos)} arquivo(s)...\n")
    total = 0
    for arquivo in arquivos:
        total += importar_arquivo(arquivo)

    print(f"\nTotal de registros importados: {total}")


if __name__ == "__main__":
    main()