"""
Conta anulacoes e sinalizacoes direto no banco.
Uso: python scripts/_debug/contar_do_banco.py
"""
import sqlite3
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent.parent
DB_PATH = BASE / "banco" / "ispaam.db"

con = sqlite3.connect(DB_PATH)

print("=" * 60)
print(" CONTAGEM DO BANCO")
print("=" * 60)

total = con.execute("SELECT COUNT(*) FROM observacoes").fetchone()[0]
print(f"\nTotal de registros: {total}")

print("\n--- Registros com dados ausentes (NULL) ---")
print(f"tmax NULL:      {con.execute('SELECT COUNT(*) FROM observacoes WHERE tmax IS NULL').fetchone()[0]}")
print(f"tmin NULL:      {con.execute('SELECT COUNT(*) FROM observacoes WHERE tmin IS NULL').fetchone()[0]}")
print(f"tmed NULL:      {con.execute('SELECT COUNT(*) FROM observacoes WHERE tmed IS NULL').fetchone()[0]}")
print(f"ev_mm_dia NULL: {con.execute('SELECT COUNT(*) FROM observacoes WHERE ev_mm_dia IS NULL').fetchone()[0]}")
print(f"ur NULL:        {con.execute('SELECT COUNT(*) FROM observacoes WHERE ur IS NULL').fetchone()[0]}")

print("\n--- Sinalizacoes (mantidas) ---")
print(f"tmax [26,27): {con.execute('SELECT COUNT(*) FROM observacoes WHERE tmax IS NOT NULL AND tmax >= 26 AND tmax < 27').fetchone()[0]}")
print(f"tmin (23,26]: {con.execute('SELECT COUNT(*) FROM observacoes WHERE tmin IS NOT NULL AND tmin > 23 AND tmin <= 26').fetchone()[0]}")

print("\n--- Sanidade (deve ser 0) ---")
print(f"tmin > tmax:            {con.execute('SELECT COUNT(*) FROM observacoes WHERE tmin IS NOT NULL AND tmax IS NOT NULL AND tmin > tmax').fetchone()[0]}")
print(f"ur > 100:               {con.execute('SELECT COUNT(*) FROM observacoes WHERE ur > 100').fetchone()[0]}")
print(f"tmax < 26:              {con.execute('SELECT COUNT(*) FROM observacoes WHERE tmax IS NOT NULL AND tmax < 26').fetchone()[0]}")
print(f"tmin fora [18,26]:      {con.execute('SELECT COUNT(*) FROM observacoes WHERE tmin IS NOT NULL AND (tmin < 18 OR tmin > 26)').fetchone()[0]}")
print(f"tmax > 45:              {con.execute('SELECT COUNT(*) FROM observacoes WHERE tmax IS NOT NULL AND tmax > 45').fetchone()[0]}")
print(f"tar fora [15,45]:       {con.execute('SELECT COUNT(*) FROM observacoes WHERE tar IS NOT NULL AND (tar < 15 OR tar > 45)').fetchone()[0]}")
print(f"ev_mm_dia fora [0,20]:  {con.execute('SELECT COUNT(*) FROM observacoes WHERE ev_mm_dia IS NOT NULL AND (ev_mm_dia < 0 OR ev_mm_dia > 20)').fetchone()[0]}")

con.close()