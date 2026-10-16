"""
verificar_a201_por_ano.py
-------------------------
Verifica se a série da A201 tem salto em algum ano.
Mostra a média de Tmax (máx. horária) por ano.
"""

import csv
from collections import defaultdict
from datetime import datetime
from pathlib import Path

BASE = Path(r"C:\Users\luizt\Desktop\ISPAAM API\agromet-ufra")
CAMINHO = BASE / "dados_A201_H_2018-01-01_2025-12-31.csv"


def para_float(s):
    if s is None:
        return None
    s = str(s).strip()
    if not s or s.lower() == "null" or s in ("-", "--", ""):
        return None
    try:
        return float(s.replace(",", "."))
    except ValueError:
        return None


def normalizar_data(s):
    s = str(s).strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s[:10], fmt)
        except ValueError:
            continue
    return None


def main():
    print("=" * 70)
    print(f" VERIFICAÇÃO DA SÉRIE A201")
    print(f" Arquivo: {CAMINHO.name}")
    print("=" * 70)

    if not CAMINHO.exists():
        print(f"\nERRO: arquivo não encontrado em {CAMINHO}")
        return

    with open(CAMINHO, encoding="utf-8") as f:
        linhas = f.readlines()

    idx_cab = next((i for i, l in enumerate(linhas) if l.startswith("Data Medicao")), None)
    if idx_cab is None:
        print("\nERRO: cabeçalho não encontrado")
        return

    cabecalho = [c.strip() for c in linhas[idx_cab].strip().split(";")]
    idx = {nome: j for j, nome in enumerate(cabecalho)}

    col_data = idx.get("Data Medicao")
    col_tmax_ant = idx.get("TEMPERATURA MAXIMA NA HORA ANT. (AUT)(°C)")

    if col_data is None or col_tmax_ant is None:
        print("\nERRO: colunas esperadas não encontradas")
        print(f"Colunas disponíveis: {list(idx.keys())[:10]}...")
        return

    # Agrupa por ano
    por_ano = defaultdict(list)
    por_mes = defaultdict(list)

    for linha in linhas[idx_cab + 1:]:
        partes = [p.strip() for p in linha.strip().split(";")]
        if len(partes) <= max(col_data, col_tmax_ant):
            continue
        dt = normalizar_data(partes[col_data])
        if dt is None:
            continue
        v = para_float(partes[col_tmax_ant])
        if v is None:
            continue
        por_ano[dt.year].append(v)
        por_mes[(dt.year, dt.month)].append(v)

    print(f"\n REGISTROS POR ANO")
    print(f" {'Ano':<6} {'N':>7} {'Média':>10} {'Mín':>8} {'Máx':>8}")
    print(" " + "-" * 45)

    for ano in sorted(por_ano):
        vals = por_ano[ano]
        media = sum(vals) / len(vals)
        print(f" {ano:<6} {len(vals):>7} {media:>+10.3f} "
              f"{min(vals):>+8.2f} {max(vals):>+8.2f}")

    # Salto entre 2020 e 2021
    if 2020 in por_ano and 2021 in por_ano:
        m2020 = sum(por_ano[2020]) / len(por_ano[2020])
        m2021 = sum(por_ano[2021]) / len(por_ano[2021])
        dif = m2021 - m2020
        print(f"\n SALTO 2020 → 2021: {dif:+.3f} °C")
        if abs(dif) > 0.5:
            print("   >>> SALTO SUSPEITO. Pode indicar mudança de sensor ou calibração.")
        else:
            print("   Dentro do esperado.")

    # Salto por mês em 2020-2021
    print(f"\n DETALHE MENSAL 2020-2021")
    print(f" {'Mês':<6} {'2020':>10} {'2021':>10} {'Dif':>10}")
    print(" " + "-" * 45)

    nomes_mes = {1:"Jan", 2:"Fev", 3:"Mar", 4:"Abr", 5:"Mai", 6:"Jun",
                 7:"Jul", 8:"Ago", 9:"Set", 10:"Out", 11:"Nov", 12:"Dez"}

    for mes in range(1, 13):
        v20 = por_mes.get((2020, mes), [])
        v21 = por_mes.get((2021, mes), [])
        if not v20 or not v21:
            continue
        m20 = sum(v20) / len(v20)
        m21 = sum(v21) / len(v21)
        d = m21 - m20
        print(f" {nomes_mes[mes]:<6} {m20:>+10.3f} {m21:>+10.3f} {d:>+10.3f}")

    print("\n" + "=" * 70)
    print(" FIM")
    print("=" * 70)


if __name__ == "__main__":
    main()