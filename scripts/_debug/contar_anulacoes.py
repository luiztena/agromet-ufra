"""
contar_anulacoes.py
-------------------
Conta anulacoes e sinalizacoes apos reimportacao.
Uso: python scripts/_debug/contar_anulacoes.py
"""
import sqlite3
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent.parent
DB_PATH = BASE / "banco" / "ispaam.db"

con = sqlite3.connect(DB_PATH)

print("=" * 60)
print(" CONTAGEM POS-REIMPORTACAO")
print("=" * 60)

# Anulacoes (valores que viraram NULL)
print("\n--- Anulacoes ---")
print("tmax < 26:", con.execute("SELECT COUNT(*) FROM observacoes WHERE tmax IS NOT NULL AND tmax < 26").fetchone()[0])
print("tmin fora [18,23]:", con.execute("SELECT COUNT(*) FROM observacoes WHERE tmin IS NOT NULL AND (tmin < 18 OR tmin > 23)").fetchone()[0])
print("ur > 100:", con.execute("SELECT COUNT(*) FROM observacoes WHERE ur IS NOT NULL AND ur > 100").fetchone()[0])
print("tar fora [15,45]:", con.execute("SELECT COUNT(*) FROM observacoes WHERE tar IS NOT NULL AND (tar < 15 OR tar > 45)").fetchone()[0])
print("ev_mm_dia fora [0,20]:", con.execute("SELECT COUNT(*) FROM observacoes WHERE ev_mm_dia IS NOT NULL AND (ev_mm_dia < 0 OR ev_mm_dia > 20)").fetchone()[0])

# Sinalizacoes (mantidos mas sinalizados)
print("\n--- Sinalizacoes (mantidos) ---")
print("tmax [26,27):", con.execute("SELECT COUNT(*) FROM observacoes WHERE tmax IS NOT NULL AND tmax >= 26 AND tmax < 27").fetchone()[0])
print("tmin (23,26]:", con.execute("SELECT COUNT(*) FROM observacoes WHERE tmin IS NOT NULL AND tmin > 23 AND tmin <= 26").fetchone()[0])

# Total
print("\n--- Totais ---")
print("Total registros:", con.execute("SELECT COUNT(*) FROM observacoes").fetchone()[0])

con.close()