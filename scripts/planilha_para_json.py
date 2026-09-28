"""
planilha_para_json.py
---------------------
Converte uma aba específica de uma planilha .xlsx no JSON bruto do ISPAAM.

- Lê a aba indicada por --aba (padrão: primeira aba).
- Converte datetime -> 'dd/mm/aaaa'
- Converte time    -> 'hh:mm'
- Converte números -> string com vírgula decimal (padrão do pipeline)
- Ignora linhas completamente vazias.
- Normaliza cabeçalhos (espaços extras, aliases, ordem).
- Trata a aba 2018 (layout diferente dos demais anos).

Uso:
    python scripts/planilha_para_json.py "dados_brutos/planilhas/Dados TAB.xlsx" --aba 2026 -o dados_brutos/dados_2026.json
"""

import argparse
import json
import sys
from datetime import datetime, time
from pathlib import Path

from openpyxl import load_workbook


# ---------------------------------------------------------------------------
# Mapeamentos de cabeçalho
# ---------------------------------------------------------------------------

# Aliases: variação -> nome canônico
ALIASES_CABECALHO = {
    "Data (dd/mm/aaaa)": "Data    (dd/mm/aaaa)",
    "Hora (hh:mm)": "Hora local (hh:mm)",
    "Prp (mm)": "Prp (mm/dia)",
    "Ev (mm) coleta": "Ev (mm)",
    "Ev (mm)*      coleta": "Ev (mm)",
    "Ev (mm)*        após enchimento": "Ev (mm)*",
    "Ev (mm)": "Ev (mm/dia)",   # cuidado: só vale quando a coluna era "Ev (mm)" simples
    "Observações": "Observadores",
}

# Mapeamento POSICIONAL para a aba 2018 (layout diferente)
# Índice no arquivo -> nome canônico
MAPA_2018 = {
    0: "Dia da semana",
    1: "Data    (dd/mm/aaaa)",
    2: "Hora local (hh:mm)",
    3: "Hora UTC (hh:mm)",
    4: "Tmáx (°C)",
    5: "Tmin (°C)",
    6: "Tméd (ºC)",      # 2018 tem Tméd na posição 6
    7: "Tar (°C)",       # Tar está na 7 (nos outros anos é 6)
    8: "TH2O ev (°C)",
    9: "U2 (m/s)",
    10: "Tar 2 (°C)",
    11: "Prp (mm/dia)",
    12: "Ev (mm)",
    13: "Ev (mm)*",
    14: "Patm (mbar)",
    15: "Tmáx Real (ºC)",
    16: "Tmin Real (ºC)",
    17: "esTU",
    18: "ea",
    19: "es",
    20: "UR (%)",
    21: "Ev (mm/dia)",
    22: "Observadores",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def formatar_valor(valor):
    """Converte um valor de célula do Excel no formato que queremos no JSON."""
    if valor is None:
        return None

    # datetime (data com ou sem hora)
    if isinstance(valor, datetime):
        if valor.hour == 0 and valor.minute == 0 and valor.second == 0:
            return f"{valor.day:02d}/{valor.month:02d}"
        else:
            return valor.strftime("%d/%m %H:%M")

    # time (hora pura)
    if isinstance(valor, time):
        return f"{valor.hour:02d}:{valor.minute:02d}"

    # string: limpa
    if isinstance(valor, str):
        s = valor.strip()
        return s if s else None

    # números -> string com vírgula decimal (compatível com JSONs antigos)
    if isinstance(valor, (int, float)):
        if isinstance(valor, float) and valor.is_integer():
            return str(int(valor))
        return str(valor).replace(".", ",")

    return str(valor)


def normalizar_cabecalho(nome, idx):
    """
    Normaliza o nome da coluna do cabeçalho:
    - Se for None, retorna 'coluna_<idx>'.
    - Se tiver alias, aplica.
    - Se tiver espaços múltiplos, colapsa.
    """
    if nome is None:
        return f"coluna_{idx}"
    if not isinstance(nome, str):
        return str(nome)

    # Colapsa espaços múltiplos (mas preserva os nomes canônicos com 4 espaços)
    nome_limpo = " ".join(nome.split()) if nome.strip() else nome

    # Se tem alias exato, aplica
    if nome in ALIASES_CABECALHO:
        return ALIASES_CABECALHO[nome]
    if nome_limpo in ALIASES_CABECALHO:
        return ALIASES_CABECALHO[nome_limpo]

    return nome


def obter_cabecalho(cabecalho_raw, aba):
    """
    Retorna a lista de nomes de coluna a usar.
    Se for a aba 2018, usa o MAPA_2018 (posicional).
    Caso contrário, normaliza por nome.
    """
    if aba and aba.strip() == "2018":
        # 2018 tem layout próprio — mapeamento posicional
        cabecalho = []
        for i in range(len(cabecalho_raw)):
            cabecalho.append(MAPA_2018.get(i, f"coluna_{i}"))
        print(f"  [2018] Usando mapeamento posicional especial")
        return cabecalho

    # Demais anos: normaliza por nome
    return [normalizar_cabecalho(c, i) for i, c in enumerate(cabecalho_raw)]


def coluna_data_canonica(aba):
    """Retorna o nome canônico da coluna de data pra cada aba."""
    return "Data    (dd/mm/aaaa)"


# ---------------------------------------------------------------------------
# Conversão
# ---------------------------------------------------------------------------

def converter(caminho_entrada: Path, caminho_saida: Path, aba: str = None):
    if not caminho_entrada.exists():
        print(f"Arquivo não encontrado: {caminho_entrada}")
        sys.exit(1)

    print(f"Lendo: {caminho_entrada}")
    wb = load_workbook(caminho_entrada, data_only=True, read_only=True)

    if aba:
        if aba not in wb.sheetnames:
            print(f"Aba '{aba}' não existe. Disponíveis: {wb.sheetnames}")
            sys.exit(1)
        ws = wb[aba]
    else:
        ws = wb[wb.sheetnames[0]]
        print(f"Usando primeira aba: '{ws.title}'")

    print(f"Aba usada: '{ws.title}'")

    linhas_iter = ws.iter_rows(values_only=True)

    # Cabeçalho
    try:
        cabecalho_raw = next(linhas_iter)
    except StopIteration:
        print("Planilha vazia.")
        sys.exit(1)

    cabecalho = obter_cabecalho(cabecalho_raw, ws.title)
    print(f"Colunas ({len(cabecalho)}): {cabecalho[:6]}...")

    coluna_data = coluna_data_canonica(ws.title)

    registros = []
    ignorados = 0

    for linha in linhas_iter:
        if all(c is None or (isinstance(c, str) and c.strip() == "") for c in linha):
            ignorados += 1
            continue

        obj = {}
        for i, valor in enumerate(linha):
            if i >= len(cabecalho):
                break
            obj[cabecalho[i]] = formatar_valor(valor)

        # Filtro: pula linhas sem Data (linhas de molde do Excel)
        if not obj.get(coluna_data):
            ignorados += 1
            continue

        registros.append(obj)

    wb.close()

    with open(caminho_saida, "w", encoding="utf-8") as f:
        json.dump(registros, f, ensure_ascii=False, indent=4)

    print(f"\n  Registros gerados: {len(registros)}")
    if ignorados:
        print(f"  Linhas vazias ignoradas: {ignorados}")
    print(f"  Salvo em: {caminho_saida}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Converte uma aba de planilha .xlsx em JSON bruto."
    )
    parser.add_argument("entrada", help="Caminho da planilha .xlsx.")
    parser.add_argument("-o", "--saida",
                        help="JSON de saída. Padrão: dados_brutos/dados_<aba>.json")
    parser.add_argument("--aba", help="Nome da aba (padrão: primeira).")
    args = parser.parse_args()

    entrada = Path(args.entrada)

    if args.saida:
        saida = Path(args.saida)
    elif args.aba:
        saida = Path("dados_brutos") / f"dados_{args.aba.strip()}.json"
    else:
        saida = Path("dados_brutos") / f"dados_{entrada.stem}.json"

    saida.parent.mkdir(parents=True, exist_ok=True)
    converter(entrada, saida, aba=args.aba)


if __name__ == "__main__":
    main()