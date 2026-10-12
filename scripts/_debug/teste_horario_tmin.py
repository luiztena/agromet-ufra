"""
teste_horario_tmin.py
---------------------
Verifica se a Tmin diária do INMET ocorre ANTES ou DEPOIS das 09:00.

Se ocorrer antes das 09:00:
    -> UFRA deveria conseguir capturar (problema é calibração)
Se ocorrer depois das 09:00:
    -> UFRA não vê (problema é horário de leitura)
"""

import csv
from pathlib import Path
from datetime import datetime
from collections import defaultdict

BASE = Path(__file__).resolve().parent.parent.parent
INMET_H_CSV = BASE / "dados_82191_H_2018-01-01_2025-12-31.csv"


def para_float(s):
    if s is None:
        return None
    s = str(s).strip()
    if not s or s.lower() == "null":
        return None
    try:
        return float(s.replace(",", "."))
    except ValueError:
        return None


def normalizar_data(s):
    s = str(s).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s[:10], fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def main():
    with open(INMET_H_CSV, encoding="utf-8") as f:
        linhas = f.readlines()

    idx_cab = next(i for i, l in enumerate(linhas) if l.startswith("Data Medicao"))
    cabecalho = [c.strip() for c in linhas[idx_cab].strip().split(";")]
    idx = {n: j for j, n in enumerate(cabecalho)}

    col_data = idx["Data Medicao"]
    col_hora = idx["Hora Medicao"]
    col_tar = idx["TEMPERATURA DO AR - BULBO SECO, HORARIA(°C)"]

    # Por dia, guarda lista de (hora, tar)
    por_dia = defaultdict(list)
    for linha in linhas[idx_cab + 1:]:
        partes = [p.strip() for p in linha.strip().split(";")]
        if len(partes) <= max(col_data, col_hora, col_tar):
            continue
        data = normalizar_data(partes[col_data])
        hora = partes[col_hora].zfill(4)
        tar = para_float(partes[col_tar])
        if not data or not hora or tar is None:
            continue
        por_dia[data].append((hora, tar))

    # Para cada dia, compara Tmin até 0900 UTC vs Tmin total
    difs = []
    for data, registros in por_dia.items():
        if len(registros) < 12:
            continue
        tar_ate_09 = [t for h, t in registros if h <= "0900"]
        tar_total = [t for h, t in registros]
        if not tar_ate_09:
            continue
        tmin_ate_09 = min(tar_ate_09)
        tmin_total = min(tar_total)
        difs.append(tmin_total - tmin_ate_09)

    if not difs:
        print("Sem dados.")
        return

    n = len(difs)
    media = sum(difs) / n
    desvio = (sum((d - media) ** 2 for d in difs) / (n - 1)) ** 0.5

    print(f"N dias analisados: {n}")
    print(f"Tmin(total) - Tmin(00h-09h UTC):")
    print(f"  Média:   {media:+.3f} °C")
    print(f"  Desvio:  {desvio:.3f} °C")
    print(f"  Mín:     {min(difs):+.3f} °C")
    print(f"  Máx:     {max(difs):+.3f} °C")
    print()
    print("Interpretação:")
    print("  Se média ≈ 0: Tmin do INMET ocorre ANTES das 09:00 UTC (12:00 local)")
    print("                 -> UFRA deveria capturar. Viés de -1 °C em Tmin")
    print("                    é então CALIBRAÇÃO ou ENTORNO.")
    print("  Se média < -0.5: Tmin do INMET ocorre DEPOIS das 09:00 UTC")
    print("                    -> UFRA não vê. Viés é HORÁRIO DE LEITURA.")


if __name__ == "__main__":
    main()