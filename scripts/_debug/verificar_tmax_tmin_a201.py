"""
verificar_tmax_tmin_a201.py
---------------------------
Decompõe a amplitude térmica da A201 em Tmax e Tmin.
Verifica qual componente mudou a partir de 2021.
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
    print("=" * 74)
    print(f" DECOMPOSIÇÃO DE TMAX E TMIN — A201")
    print("=" * 74)

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

    # Extrai Tmax e Tmin diárias
    por_ano = defaultdict(lambda: {"tmax": [], "tmin": [], "ampl": []})
    for data, vals in por_dia.items():
        if not vals["tmax"] or not vals["tmin"]:
            continue
        tmax_dia = max(vals["tmax"])
        tmin_dia = min(vals["tmin"])
        por_ano[data.year]["tmax"].append(tmax_dia)
        por_ano[data.year]["tmin"].append(tmin_dia)
        por_ano[data.year]["ampl"].append(tmax_dia - tmin_dia)

    print(f"\n TMAX DIÁRIA MÉDIA POR ANO")
    print(f" {'Ano':<6} {'N':>6} {'Tmax':>10} {'Tmin':>10} {'Amplitude':>12}")
    print(" " + "-" * 50)

    medias = {}
    for ano in sorted(por_ano):
        d = por_ano[ano]
        n = len(d["tmax"])
        m_tmax = sum(d["tmax"]) / n
        m_tmin = sum(d["tmin"]) / n
        m_ampl = sum(d["ampl"]) / n
        print(f" {ano:<6} {n:>6} {m_tmax:>+10.3f} {m_tmin:>+10.3f} {m_ampl:>+12.3f}")
        medias[ano] = {"tmax": m_tmax, "tmin": m_tmin, "ampl": m_ampl}

    # Comparação de períodos
    def media_periodo(chave, anos):
        vals = [medias[a][chave] for a in anos if a in medias]
        return sum(vals) / len(vals) if vals else None

    pre_anos = [2018, 2019, 2020]
    pos_anos = [2021, 2022, 2023]

    print(f"\n DECOMPOSIÇÃO DA MUDANÇA (2021-2023 vs 2018-2020)")
    print(" " + "-" * 60)

    for chave in ["tmax", "tmin", "ampl"]:
        pre = media_periodo(chave, pre_anos)
        pos = media_periodo(chave, pos_anos)
        dif = pos - pre
        print(f" {chave.upper():<10}: {pre:+.3f} -> {pos:+.3f}  (diferença: {dif:+.3f} °C)")

    # Diagnóstico
    dif_tmax = media_periodo("tmax", pos_anos) - media_periodo("tmax", pre_anos)
    dif_tmin = media_periodo("tmin", pos_anos) - media_periodo("tmin", pre_anos)

    print(f"\n DIAGNÓSTICO")
    print(" " + "-" * 60)

    if abs(dif_tmax) > abs(dif_tmin):
        print(f"   Tmax mudou mais ({dif_tmax:+.3f} vs {dif_tmin:+.3f})")
        print(f"   >>> A A201 passou a registrar Tmax mais alta após 2021.")
    else:
        print(f"   Tmin mudou mais ({dif_tmin:+.3f} vs {dif_tmax:+.3f})")
        print(f"   >>> A A201 passou a registrar Tmin mais baixa após 2021.")

    print("\n" + "=" * 74)
    print(" FIM")
    print("=" * 74)


if __name__ == "__main__":
    main()