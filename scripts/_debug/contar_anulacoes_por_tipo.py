"""
contar_anulacoes_por_tipo.py
----------------------------
Conta os avisos do relatorio_import_v2.txt agrupados por tipo.
Uso: python scripts/_debug/contar_anulacoes_por_tipo.py
"""
from collections import Counter
from pathlib import Path
import re

BASE = Path(__file__).resolve().parent.parent.parent
RELATORIO = BASE / "relatorio_import_v2.txt"

# Padroes que identificam o tipo de aviso
PADROES = {
    "tmed sem tmax/tmin": r"tmed \(.+\) sem tmax/tmin",
    "tmed outlier": r"tmed: outlier",
    "ev_mm_dia sem ev_mm": r"ev_mm_dia \(.+\) sem ev_mm",
    "ev_mm_dia outlier": r"ev_mm_dia: outlier",
    "tmax outlier": r"tmax: outlier",
    "tmax [26,27) sinalizado": r"tmax \(.+\) entre 26-27",
    "tmin outlier": r"tmin: outlier",
    "tmin (23,26] sinalizado": r"tmin \(.+\) entre 23-26",
    "tmin > tmax": r"tmin \(.+\) > tmax",
    "ur outlier": r"ur: outlier",
    "tar outlier": r"tar: outlier",
    "prp outlier": r"prp: outlier",
}

contagem = Counter()
total_linhas = 0

with open(RELATORIO, encoding="utf-8", errors="ignore") as f:
    for linha in f:
        linha = linha.strip()
        if not linha or not linha[0].isdigit():
            continue
        # Linhas de aviso comecam com data_iso
        if re.match(r"^\d{4}-\d{2}-\d{2}", linha):
            total_linhas += 1
            for tipo, padrao in PADROES.items():
                if re.search(padrao, linha):
                    contagem[tipo] += 1
                    break

print("=" * 60)
print(" AVISOS POR TIPO (relatorio_import_v2.txt)")
print("=" * 60)
print()
print(f"Total de avisos: {total_linhas}")
print()
print("--- Por tipo ---")
for tipo, n in sorted(contagem.items(), key=lambda x: -x[1]):
    print(f"  {tipo:35s} {n}")
print()

# Interpretacao
anulacoes = sum(n for tipo, n in contagem.items() if "sinalizado" not in tipo)
sinalizacoes = sum(n for tipo, n in contagem.items() if "sinalizado" in tipo)
print(f"ANULACOES (valores viraram NULL): {anulacoes}")
print(f"SINALIZACOES (valores mantidos):  {sinalizacoes}")