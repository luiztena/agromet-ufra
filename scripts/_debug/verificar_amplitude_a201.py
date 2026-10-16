"""
verificar_amplitude_a201.py
---------------------------
Verifica se a amplitude térmica diária (Tmax - Tmin) da A201 mudou
entre 2018-2020 e 2021-2025. Isso indicaria mudança de sítio.
"""

import math
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
    print(f" VERIFICAÇÃO DA AMPLITUDE TÉRMICA — A201")
    print("=" * 70)

    with open(CAMINHO, encoding="utf-8") as f:
        linhas = f.readlines()

    idx_cab = next((i for i, l in enumerate(linhas) if l.startswith("Data Medicao")), None)
    cabecalho = [c.strip() for c in linhas[idx_cab].strip().split(";")]
    idx = {nome: j for j, nome in enumerate(cabecalho)}

    col_data = idx["Data Medicao"]
    col_tmax_ant = idx["TEMPERATURA MAXIMA NA HORA ANT. (AUT)(°C)"]
    col_tmin_ant = idx["TEMPERATURA MINIMA NA HORA ANT. (AUT)(°C)"]

    # Agrupa por dia
    por_dia = defaultdict(lambda: {"tmax": [], "tmin": []})

    for linha in linhas[idx_cab + 1:]:
        partes = [p.strip() for p in linha.strip().split(";")]
        if len(partes) <= max(col_data, col_tmax_ant, col_tmin_ant):
            continue
        dt = normalizar_data(partes[col_data])
        if dt is None:
            continue
        tmax = para_float(partes[col_tmax_ant])
        tmin = para_float(partes[col_tmin_ant])
        if tmax is not None:
            por_dia[dt.date()]["tmax"].append(tmax)
        if tmin is not None:
            por_dia[dt.date()]["tmin"].append(tmin)

    # Amplitude diária
    por_ano = defaultdict(list)
    for data, vals in por_dia.items():
        if not vals["tmax"] or not vals["tmin"]:
            continue
        tmax_dia = max(vals["tmax"])
        tmin_dia = min(vals["tmin"])
        amplitude = tmax_dia - tmin_dia
        por_ano[data.year].append(amplitude)

    print(f"\n AMPLITUDE TÉRMICA MÉDIA (Tmax - Tmin) POR ANO")
    print(f" {'Ano':<6} {'N':>6} {'Amplitude':>12} {'Desvio':>10}")
    print(" " + "-" * 45)

    amplitudes_por_ano = {}
    for ano in sorted(por_ano):
        vals = por_ano[ano]
        n = len(vals)
        media = sum(vals) / n
        var = sum((v - media) ** 2 for v in vals) / n
        desvio = math.sqrt(var)
        print(f" {ano:<6} {n:>6} {media:>+12.3f} {desvio:>10.3f}")
        amplitudes_por_ano[ano] = media

    # Comparação
    if all(a in amplitudes_por_ano for a in (2018, 2019, 2020, 2021, 2022)):
        pre = (amplitudes_por_ano[2018] + amplitudes_por_ano[2019] +
               amplitudes_por_ano[2020]) / 3
        pos = (amplitudes_por_ano[2021] + amplitudes_por_ano[2022] +
               amplitudes_por_ano[2023]) / 3
        print(f"\n COMPARAÇÃO DE PERÍODOS")
        print(f"   Média 2018-2020: {pre:+.3f} °C")
        print(f"   Média 2021-2023: {pos:+.3f} °C")
        print(f"   Diferença:       {pos - pre:+.3f} °C")
        if abs(pos - pre) > 0.5:
            print("   >>> AMPLITUDE MUDOU. Reforça hipótese de mudança de sítio.")
        else:
            print("   Amplitude estável. Mudança de sítio é menos provável.")


if __name__ == "__main__":
    main()