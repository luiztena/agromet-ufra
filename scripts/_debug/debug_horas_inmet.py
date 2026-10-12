"""
debug_horas_inmet.py
--------------------
Mostra as primeiras linhas do CSV horário e os valores de hora.
"""

import csv
from pathlib import Path
from collections import Counter

BASE = Path(__file__).resolve().parent.parent.parent
INMET_H_CSV = BASE / "dados_82191_H_2018-01-01_2025-12-31.csv"

with open(INMET_H_CSV, encoding="utf-8") as f:
    linhas = f.readlines()

# Acha o cabeçalho
idx_cab = next(i for i, l in enumerate(linhas) if l.startswith("Data Medicao"))
print(f"Cabeçalho na linha {idx_cab}")
print()

# Mostra o cabeçalho
cabecalho = [c.strip() for c in linhas[idx_cab].strip().split(";")]
print("Colunas:")
for i, c in enumerate(cabecalho):
    print(f"  [{i}] {c}")
print()

# Mostra 10 linhas de dados
print("Primeiras 10 linhas de dados:")
for linha in linhas[idx_cab + 1:idx_cab + 11]:
    partes = [p.strip() for p in linha.strip().split(";")]
    if len(partes) < 2:
        continue
    print(f"  Data={partes[0]!r}  Hora={partes[1]!r}  Tar={partes[2]!r}")
print()

# Distribuição de horas
print("Distribuição de valores de Hora Medicao (primeiros 5000 registros):")
horas = Counter()
for linha in linhas[idx_cab + 1:idx_cab + 5001]:
    partes = [p.strip() for p in linha.strip().split(";")]
    if len(partes) < 2:
        continue
    horas[partes[1]] += 1
for h, n in sorted(horas.items())[:30]:
    print(f"  {h!r}: {n}")