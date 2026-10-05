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
- Valida coerência entre dia_semana e data (evita lixo).

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

ALIASES_CABECALHO = {
    "Data (dd/mm/aaaa)": "Data    (dd/mm/aaaa)",
    "Hora (hh:mm)": "Hora local (hh:mm)",
    "Prp (mm)": "Prp (mm/dia)",
    "Ev (mm) coleta": "Ev (mm)",
    "Ev (mm)*      coleta": "Ev (mm)",
    "Ev (mm)*        após enchimento": "Ev (mm)*",
    "Ev (mm)": "Ev (mm/dia)",
    "Observações": "Observadores",
}

MAPA_2018 = {
    0: "Dia da semana",
    1: "Data    (dd/mm/aaaa)",
    2: "Hora local (hh:mm)",
    3: "Hora UTC (hh:mm)",
    4: "Tmáx (°C)",
    5: "Tmin (°C)",
    6: "Tméd (ºC)",
    7: "Tar (°C)",
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
# Normalizacao de dia da semana (para validacao)
# ---------------------------------------------------------------------------

_DIAS_SEMANA = ["segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo"]

_MAPA_DIA_SEMANA = {
    "seg": "segunda", "segunda": "segunda", "segunda-feira": "segunda",
    "ter": "terca",   "terca": "terca",     "terca-feira": "terca",
    "qua": "quarta",  "quarta": "quarta",   "quarta-feira": "quarta",
    "qui": "quinta",  "quinta": "quinta",   "quinta-feira": "quinta",
    "sex": "sexta",   "sexta": "sexta",     "sexta-feira": "sexta",
    "sab": "sabado",  "sabado": "sabado",
    "dom": "domingo", "domingo": "domingo",
}


def _normalizar_dia_semana(s):
    """Normaliza 'seg' -> 'segunda', 'Sexta-feira' -> 'sexta', etc."""
    if not s:
        return None
    s = s.lower().strip()
    # Remove acentos
    s = (s.replace("á", "a").replace("ã", "a").replace("â", "a")
           .replace("é", "e").replace("ê", "e")
           .replace("í", "i")
           .replace("ó", "o").replace("ô", "o").replace("õ", "o")
           .replace("ú", "u")
           .replace("ç", "c"))
    return _MAPA_DIA_SEMANA.get(s, s)


def _dia_semana_confere(data_dd_mm, dia_semana_str, ano):
    """
    Verifica se o dia da semana bate com a data (formato dd/mm).
    Retorna True se OK, False se inconsistente, True se nao der pra validar.
    """
    if not data_dd_mm or not dia_semana_str or not ano:
        return True  # sem dado suficiente, nao valida

    partes = str(data_dd_mm).split("/")
    if len(partes) < 2:
        return True

    try:
        dd = int(partes[0])
        mm = int(partes[1])
        data = datetime(ano, mm, dd)
    except (ValueError, IndexError):
        return True  # data invalida, deixa passar (sera tratada depois)

    dia_real = _DIAS_SEMANA[data.weekday()]
    dia_planilha = _normalizar_dia_semana(dia_semana_str)

    if dia_planilha is None:
        return True  # sem dia da semana na planilha, deixa passar

    return dia_planilha == dia_real


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def formatar_valor(valor):
    """Converte um valor de célula do Excel no formato que queremos no JSON."""
    if valor is None:
        return None

    if isinstance(valor, datetime):
        if valor.hour == 0 and valor.minute == 0 and valor.second == 0:
            return f"{valor.day:02d}/{valor.month:02d}"
        else:
            return valor.strftime("%d/%m %H:%M")

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
    if nome is None:
        return f"coluna_{idx}"
    if not isinstance(nome, str):
        return str(nome)

    nome_limpo = " ".join(nome.split()) if nome.strip() else nome

    if nome in ALIASES_CABECALHO:
        return ALIASES_CABECALHO[nome]
    if nome_limpo in ALIASES_CABECALHO:
        return ALIASES_CABECALHO[nome_limpo]

    return nome


def obter_cabecalho(cabecalho_raw, aba):
    if aba and aba.strip() == "2018":
        cabecalho = []
        for i in range(len(cabecalho_raw)):
            cabecalho.append(MAPA_2018.get(i, f"coluna_{i}"))
        print(f"  [2018] Usando mapeamento posicional especial")
        return cabecalho

    return [normalizar_cabecalho(c, i) for i, c in enumerate(cabecalho_raw)]


def coluna_data_canonica(aba):
    return "Data    (dd/mm/aaaa)"


# ---------------------------------------------------------------------------
# Conversão
# ---------------------------------------------------------------------------

def converter(caminho_entrada: Path, caminho_saida: Path, aba: str = None):
    if not caminho_entrada.exists():
        print(f"Arquivo não encontrado: {caminho_entrada}")
        sys.exit(1)

    # Extrai o ano da aba para validar dia da semana
    ano_aba = None
    if aba:
        try:
            ano_aba = int(aba.strip())
        except ValueError:
            ano_aba = None

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
    if ano_aba:
        print(f"Ano inferido (para validação): {ano_aba}")

    linhas_iter = ws.iter_rows(values_only=True)

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
    rejeitados_dia_semana = 0

    for linha in linhas_iter:
        if all(c is None or (isinstance(c, str) and c.strip() == "") for c in linha):
            ignorados += 1
            continue

        obj = {}
        for i, valor in enumerate(linha):
            if i >= len(cabecalho):
                break
            obj[cabecalho[i]] = formatar_valor(valor)

        if not obj.get(coluna_data):
            ignorados += 1
            continue

        # ===== VALIDAÇÃO: dia da semana bate com a data? =====
        data_str = obj.get(coluna_data)
        dia_semana_str = obj.get("Dia da semana")
        if not _dia_semana_confere(data_str, dia_semana_str, ano_aba):
            print(f"  [SKIP] {data_str} ({dia_semana_str}) — dia da semana inconsistente")
            rejeitados_dia_semana += 1
            continue

        registros.append(obj)

    wb.close()

    with open(caminho_saida, "w", encoding="utf-8") as f:
        json.dump(registros, f, ensure_ascii=False, indent=4)

    print(f"\n  Registros gerados: {len(registros)}")
    if ignorados:
        print(f"  Linhas vazias ignoradas: {ignorados}")
    if rejeitados_dia_semana:
        print(f"  Linhas rejeitadas (dia da semana inconsistente): {rejeitados_dia_semana}")
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