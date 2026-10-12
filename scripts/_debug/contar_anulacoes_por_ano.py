"""
Conta anulacoes e sinalizacoes por ano, reconstruindo o que o relatorio mostra.
Uso: python scripts/_debug/contar_anulacoes_por_ano.py
"""
import json
import sqlite3
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent.parent
PASTA = BASE / "dados_brutos"
DB_PATH = BASE / "banco" / "ispaam.db"

# Regras (espelho do importar_json.py)
REGRAS = [
    ("tar",        15.0,  45.0),
    ("tmax",       26.0,  45.0),
    ("tmin",       18.0,  26.0),
    ("tmax_real",  26.0,  45.0),
    ("tmin_real",  18.0,  26.0),
    ("tmed",       10.0,  40.0),
    ("ur",          0.0, 100.0),
    ("prp",         0.0, 500.0),
    ("ev_mm_dia",   0.0,  20.0),
]

print("=" * 60)
print(" ANULACOES E SINALIZACOES POR ANO (reconstruido do JSON)")
print("=" * 60)
print()

total_anulacoes = 0
total_sinalizacoes = 0

for arquivo in sorted(PASTA.glob("dados_*.json")):
    ano = arquivo.stem.split("_")[1]

    with open(arquivo, encoding="utf-8") as f:
        linhas = json.load(f)

    anulacoes_ano = 0
    sinalizacoes_ano = 0

    for linha in linhas:
        # Anulacoes por faixa
        for campo, mn, mx in REGRAS:
            # Busca a chave (varios nomes possiveis)
            chaves_possiveis = {
                "tar": ["Tar (°C)"],
                "tmax": ["Tmáx (°C)"],
                "tmin": ["Tmin (°C)"],
                "tmax_real": ["Tmáx Real (ºC)"],
                "tmin_real": ["Tmin Real (ºC)"],
                "tmed": ["Tméd (ºC)"],
                "ur": ["UR (%)"],
                "prp": ["Prp (mm/dia)"],
                "ev_mm_dia": ["Ev (mm/dia)"],
            }.get(campo, [campo])

            valor_raw = None
            for chave in chaves_possiveis:
                if chave in linha:
                    valor_raw = linha[chave]
                    break

            if valor_raw is None:
                continue

            try:
                v = float(str(valor_raw).replace(",", "."))
            except (ValueError, TypeError):
                continue

            if not (mn <= v <= mx):
                anulacoes_ano += 1

        # Sinalizacoes
        # tmax [26, 27)
        try:
            tmax = linha.get("Tmáx (°C)")
            if tmax is not None:
                tmax_f = float(str(tmax).replace(",", "."))
                if 26.0 <= tmax_f < 27.0:
                    sinalizacoes_ano += 1
        except (ValueError, TypeError):
            pass

        # tmin (23, 26]
        try:
            tmin = linha.get("Tmin (°C)")
            if tmin is not None:
                tmin_f = float(str(tmin).replace(",", "."))
                if 23.0 < tmin_f <= 26.0:
                    sinalizacoes_ano += 1
        except (ValueError, TypeError):
            pass

    print(f"{ano}: anulacoes={anulacoes_ano:4d}  sinalizacoes={sinalizacoes_ano:4d}")
    total_anulacoes += anulacoes_ano
    total_sinalizacoes += sinalizacoes_ano

print()
print(f"TOTAL anulacoes:     {total_anulacoes}")
print(f"TOTAL sinalizacoes:  {total_sinalizacoes}")