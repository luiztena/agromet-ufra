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
- A coluna "dia_semana" é normalizada para forma canônica.
- Chaves em mojibake (ex.: "TmÃ©d") são corrigidas para UTF-8 ("Tméd").

VALIDAÇÃO (aplicada antes do INSERT):
- tar fora de [15, 45] °C          -> NULL
- tmax fora de [15, 45] °C         -> NULL
- tmin fora de [10, 35] °C         -> NULL
- ur fora de [0, 100] %            -> se > 100: cap em 100
                                     se < 0:   NULL
- tmin > tmax                      -> ambos NULL
- prp < 0 ou > 500 mm              -> NULL
- ev_mm_dia < 0 ou > 20 mm         -> NULL

Uso:
    python scripts/importar_json.py
    python scripts/importar_json.py dados_brutos/dados_2026.json
    python scripts/importar_json.py --relatorio-limpeza
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


# ---------------------------------------------------------------------------
# Regras de validação (campo_db, min, max, acao)
#   acao: 'null'  -> fora da faixa vira None
#         'cap'   -> clampa no limite mais proximo
# ---------------------------------------------------------------------------
REGRAS_VALIDACAO = [
    ("tar",        15.0,  45.0, "null"),
    ("tmax",       15.0,  45.0, "null"),
    ("tmin",       10.0,  35.0, "null"),
    ("tmax_real",  15.0,  45.0, "null"),
    ("tmin_real",  10.0,  35.0, "null"),
    ("tmed",       10.0,  40.0, "null"),
    ("ur",          0.0, 100.0, "cap"),
    ("prp",         0.0, 500.0, "null"),
    ("ev_mm_dia",   0.0,  20.0, "null"),
]


# ---------------------------------------------------------------------------
# Mapeamento: chave no JSON (UTF-8 limpo) -> coluna no banco
# O corrigir_mojibake() normaliza as chaves do JSON antes do lookup,
# então aqui usamos os nomes corretos (com acento).
# ---------------------------------------------------------------------------
MAPA_CAMPOS = {
    "Tar (°C)":               "tar",
    "TH2O ev (°C)":           "th2o_ev",
    "Tmáx (°C)":              "tmax",
    "Tmin (°C)":              "tmin",
    "Tmáx Real (ºC)":         "tmax_real",
    "Tmin Real (ºC)":         "tmin_real",
    "Tméd (ºC)":              "tmed",
    "UR (%)":                 "ur",
    "esTU":                   "estu",
    "ea":                     "ea",
    "es":                     "es",
    "Direção do vento":       "direcao_vento",
    "U2 (m/s)":               "u2",
    "Prp (mm/dia)":           "prp",
    "Soma de Prp (mm/dia)":   "soma_prp",
    "pluv. alternativo (ml)": "pluv_alt",
    "Ev (mm)":                "ev_mm",
    "Ev (mm)*":               "ev_mm_ast",
    "Ev (mm/dia)":            "ev_mm_dia",
    "Tanque":                 "tanque",
    "Patm (mbar)":            "patm",
    "Evento":                 "evento",
    "Visibilidade":           "visibilidade",
    "Nuvem":                  "nuvem",
    "Cobertura do céu":       "cobertura_ceu",
    "Observadores":           "observadores",
}

CAMPOS_TEXTO = {
    "direcao_vento", "evento", "visibilidade",
    "nuvem", "cobertura_ceu", "observadores",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def corrigir_mojibake(s):
    """Corrige mojibake tipo 'TmÃ©d' -> 'Tméd'."""
    if not isinstance(s, str):
        return s
    try:
        return s.encode("latin1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


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


def normalizar_dia_semana(valor):
    if not valor:
        return None
    valor = valor.strip().lower()
    valor = (valor
             .replace("á", "a").replace("ã", "a").replace("â", "a")
             .replace("é", "e").replace("ê", "e")
             .replace("í", "i")
             .replace("ó", "o").replace("ô", "o").replace("õ", "o")
             .replace("ú", "u")
             .replace("ç", "c"))
    mapa = {
        "seg": "segunda", "segunda": "segunda", "segunda-feira": "segunda",
        "ter": "terca",   "terca": "terca",     "terca-feira": "terca",
        "qua": "quarta",  "quarta": "quarta",   "quarta-feira": "quarta",
        "qui": "quinta",  "quinta": "quinta",   "quinta-feira": "quinta",
        "sex": "sexta",   "sexta": "sexta",     "sexta-feira": "sexta",
        "sab": "sabado",  "sabado": "sabado",
        "dom": "domingo", "domingo": "domingo",
    }
    return mapa.get(valor, valor)


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


def obter_dia_semana(linha):
    """As chaves já vêm corrigidas pelo corrigir_mojibake()."""
    valor_cru = (
        linha.get("Dia da semana")
        or linha.get("coluna_0")
        or linha.get("  ")
        or linha.get(" ")
    )
    return normalizar_dia_semana(valor_cru)


# ---------------------------------------------------------------------------
# Validação
# ---------------------------------------------------------------------------
def validar_valor(valor, minimo, maximo, acao):
    """Retorna (valor_ajustado, motivo_alteracao ou None)."""
    if valor is None:
        return valor, None

    if minimo <= valor <= maximo:
        return valor, None

    if acao == "cap":
        novo = max(minimo, min(maximo, valor))
        return novo, f"cap {valor} -> {novo}"
    elif acao == "null":
        return None, f"outlier {valor} (faixa {minimo}..{maximo}) -> null"
    return valor, None


def validar_registro(valores, data_iso=None, hora=None):
    """
    Aplica as regras de validação no dict de valores (já convertidos pra float).
    Retorna (valores_ajustados, lista_avisos).
    """
    avisos = []

    for campo, mn, mx, acao in REGRAS_VALIDACAO:
        if campo not in valores:
            continue
        v_orig = valores[campo]
        novo, motivo = validar_valor(v_orig, mn, mx, acao)
        if motivo:
            valores[campo] = novo
            avisos.append(f"{campo}: {motivo}")

    # Regra cruzada tmin > tmax
    tmin = valores.get("tmin")
    tmax = valores.get("tmax")
    if tmin is not None and tmax is not None:
        if tmin > tmax:
            avisos.append(f"tmin ({tmin}) > tmax ({tmax}) -> ambos null")
            valores["tmin"] = None
            valores["tmax"] = None

    if avisos and data_iso:
        prefixo = f"{data_iso} {hora or ''}".strip()
        avisos = [f"{prefixo}: {a}" for a in avisos]

    return valores, avisos


# ---------------------------------------------------------------------------
# Importação
# ---------------------------------------------------------------------------
def importar_arquivo(caminho: Path, relatorio_limpeza=False):
    ano = extrair_ano(caminho.name)
    if ano is None:
        print(f"  [SKIP] {caminho.name}: nome não segue o padrão dados_YYYY.json")
        return 0

    with open(caminho, encoding="utf-8") as f:
        linhas = json.load(f)

    # Corrige encoding das chaves (mojibake do Excel) ANTES de qualquer lookup
    linhas = [
        {corrigir_mojibake(k): v for k, v in linha.items()}
        for linha in linhas
    ]

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
    total_avisos = 0

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
            "dia_semana":    obter_dia_semana(linha),
            "protocolo":     protocolo,
        }

        for chave_json, coluna_db in MAPA_CAMPOS.items():
            raw = linha.get(chave_json)
            if coluna_db in CAMPOS_TEXTO:
                valores[coluna_db] = limpar_texto(raw)
            else:
                valores[coluna_db] = para_float(raw)

        # ===== VALIDAÇÃO =====
        valores, avisos = validar_registro(valores, data_iso, hora)
        if avisos:
            total_avisos += len(avisos)
            if relatorio_limpeza:
                for a in avisos:
                    print(f"    {a}")

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
    if total_avisos:
        print(f"    Avisos:     {total_avisos} valores corrigidos/nulados")

    return inseridos


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    if not CAMINHO_BANCO.exists():
        print(f"Banco não encontrado: {CAMINHO_BANCO}")
        print("Rode 'python scripts/criar_banco.py' primeiro.")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Importa JSONs para o banco ispaam.db.")
    parser.add_argument("arquivo", nargs="?",
                        help="Arquivo específico. Se omitido, importa todos os dados_*.json de dados_brutos/.")
    parser.add_argument("--relatorio-limpeza", action="store_true",
                        help="Imprime cada valor corrigido/nulado pela validação.")
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
        total += importar_arquivo(arquivo, relatorio_limpeza=args.relatorio_limpeza)

    print(f"\nTotal de registros importados: {total}")


if __name__ == "__main__":
    main()