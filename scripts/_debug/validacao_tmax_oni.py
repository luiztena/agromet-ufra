"""
validacao_tmax_oni.py
---------------------
Correlação entre viés anual de Tmax e o índice ONI.

ONI anual médio (NOAA CPC, valores aproximados):
  2018: -0.4  (La Niña fraca no início, depois neutro)
  2019: +0.4  (El Niño fraco)
  2020: -0.6  (La Niña)
  2021: -0.9  (La Niña)
  2022: -1.0  (La Niña)
  2023: +1.5  (El Niño forte)
  2024: +0.5  (El Niño enfraquecendo)
  2025: -0.3  (La Niña fraca)
"""

import csv
import math
import sqlite3
import statistics
from pathlib import Path
from datetime import datetime
from collections import defaultdict

BASE = Path(r"C:\Users\luizt\Desktop\ISPAAM API\agromet-ufra")
DB_PATH = BASE / "banco" / "ispaam.db"
INMET_D_82191 = BASE / "dados_82191_D_2018-01-01_2025-12-31.csv"

SAIDA = BASE / "validacao_tmax_oni.csv"

ONI = {
    2018: -0.4,
    2019: +0.4,
    2020: -0.6,
    2021: -0.9,
    2022: -1.0,
    2023: +1.5,
    2024: +0.5,
    2025: -0.3,
}


def para_float(s):
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
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
            return datetime.strptime(s[:10], fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def pearson(xs, ys):
    n = len(xs)
    if n < 2:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((xs[i] - mx) * (ys[i] - my) for i in range(n)) / n
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs) / n)
    dy = math.sqrt(sum((y - my) ** 2 for y in ys) / n)
    if dx * dy == 0:
        return None
    return cov / (dx * dy)


def carregar_ufra(caminho_db):
    con = sqlite3.connect(caminho_db)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute("PRAGMA table_info(observacoes)")
    cols = {r[1] for r in cur.fetchall()}
    c_tmax = "tmax_real" if "tmax_real" in cols else "tmax"
    sql = f"SELECT data_iso, {c_tmax} AS tmax FROM observacoes WHERE hora_local = '09:00'"
    ufra = {}
    for row in cur.execute(sql):
        d = row["data_iso"]
        if not d:
            continue
        v = para_float(row["tmax"])
        if v is not None:
            ufra[d] = v
    con.close()
    return ufra


def carregar_inmet(caminho):
    with open(caminho, encoding="utf-8") as f:
        linhas = f.readlines()
    idx_cab = next((i for i, l in enumerate(linhas) if l.startswith("Data Medicao")), None)
    cabecalho = [c.strip() for c in linhas[idx_cab].strip().split(";")]
    idx = {nome: j for j, nome in enumerate(cabecalho)}
    col_data = idx["Data Medicao"]
    col_tmax = idx["TEMPERATURA MAXIMA, DIARIA(°C)"]
    inmet = {}
    for linha in linhas[idx_cab + 1:]:
        partes = [p.strip() for p in linha.strip().split(";")]
        if len(partes) <= max(col_data, col_tmax):
            continue
        d = normalizar_data(partes[col_data])
        if not d:
            continue
        v = para_float(partes[col_tmax])
        if v is not None:
            inmet[d] = v
    return inmet


def main():
    print("=" * 78)
    print(" CORRELAÇÃO VIÉS TMAX × ONI")
    print("=" * 78)

    ufra = carregar_ufra(DB_PATH)
    inmet = carregar_inmet(INMET_D_82191)

    # Viés por ano
    por_ano = defaultdict(list)
    for d in sorted(set(ufra) & set(inmet)):
        ano = int(d[:4])
        por_ano[ano].append(ufra[d] - inmet[d])

    print(f"\n {'Ano':<6} {'N':>5} {'Viés':>9} {'ONI':>7}")
    print(" " + "-" * 30)

    anos_v = []
    vieses = []
    onis = []
    detalhes = []

    for ano in sorted(por_ano):
        difs = por_ano[ano]
        n = len(difs)
        vies = sum(difs) / n
        oni = ONI.get(ano)
        print(f" {ano:<6} {n:>5} {vies:>+9.3f} {oni:>+7.2f}" if oni is not None
              else f" {ano:<6} {n:>5} {vies:>+9.3f}    —")
        if oni is not None:
            anos_v.append(ano)
            vieses.append(vies)
            onis.append(oni)
            detalhes.append({"ano": ano, "n": n, "vies": vies, "oni": oni})

    # Correlação
    r = pearson(onis, vieses)
    print("\n" + "=" * 78)
    print(" RESULTADO")
    print("=" * 78)
    print(f"\n N anos:      {len(anos_v)}")
    print(f" Correlação:  r = {r:+.3f}" if r is not None else " Correlação:  não calculável")

    if r is not None:
        r2 = r * r
        print(f" R²:          {r2:.3f}")
        print(f"\n Interpretação:")
        if abs(r) < 0.3:
            print("   Correlação fraca. Sem modulação aparente por ENOS.")
        elif abs(r) < 0.6:
            print("   Correlação moderada. Pode haver modulação, mas amostra pequena (7 anos).")
        else:
            print("   Correlação forte. Sinal consistente de modulação por ENOS.")
        print(f"\n   Sinal: {'positivo' if r > 0 else 'negativo'}")
        if r > 0:
            print("   ONI maior (El Niño) → viés maior (mais quente na UFRA)")
        else:
            print("   ONI menor (La Niña) → viés maior")

    # Exportar
    with open(SAIDA, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["ano", "n", "vies", "oni"])
        w.writeheader()
        for d in detalhes:
            w.writerow(d)
    print(f"\n  {SAIDA}")

    print("\n" + "=" * 78)
    print(" FIM")
    print("=" * 78)


if __name__ == "__main__":
    main()