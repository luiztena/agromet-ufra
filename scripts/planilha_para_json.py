"""
planilha_para_json.py
---------------------
Converte uma aba específica de uma planilha .xlsx no JSON bruto do ISPAAM.

- Lê a aba indicada por --aba (padrão: primeira aba).
- Converte datetime -> 'dd/mm/aaaa'
- Converte time    -> 'hh:mm'
- Converte números -> string com vírgula decimal (padrão do pipeline)
- Ignora linhas completamente vazias.
- Preserva o cabeçalho original (inclusive a coluna '  ' com dois espaços).

Uso:
    python scripts/planilha_para_json.py "dados_brutos/planilhas/Dados TAB.xlsx" --aba 2026 -o dados_brutos/dados_2026.json
    """

import argparse
import json
import sys
from datetime import datetime, time
from pathlib import Path

from openpyxl import load_workbook


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
        # Se for inteiro "redondo", mantém sem casas decimais
        if isinstance(valor, float) and valor.is_integer():
            return str(int(valor))
        return str(valor).replace(".", ",")

    return str(valor)


def limpar_cabecalho(valor, idx):
    """Normaliza o nome da coluna do cabeçalho."""
    if valor is None:
        return f"coluna_{idx}"
    if isinstance(valor, str):
        return valor  # preserva, inclusive '  '
    return str(valor)


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

    cabecalho = [limpar_cabecalho(c, i) for i, c in enumerate(cabecalho_raw)]
    print(f"Colunas ({len(cabecalho)}): {cabecalho[:6]}...")

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
        if not obj.get("Data    (dd/mm/aaaa)"):
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