"""
validacao_tmax_a201.py
----------------------
Compara Tmax UFRA contra INMET A201 (automática).
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
INMET_A201 = BASE / "dados_A201_H_2018-01-01_2025-12-31.csv"

SAIDA = BASE / "validacao_tmax_a201.csv"


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


def ic95(valores):
    n = len(valores)
    if n < 2:
        return (None, None)
    media = sum(valores) / n
    var = sum((v - media) ** 2 for v in valores) / (n - 1)
    se = math.sqrt(var / n)
    return (media - 1.96 * se, media + 1.96 * se)


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


def willmott_d(obs, mod):
    n = len(obs)
    if n == 0:
        return None
    media_obs = sum(obs) / n
    num = sum((obs[i] - mod[i]) ** 2 for i in range(n))
    den = sum((abs(obs[i] - media_obs) + abs(mod[i] - media_obs)) ** 2 for i in range(n))
    if den == 0:
        return None
    return 1 - (num / den)


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


def carregar_a201_diario(caminho):
    """
    A201 traz valores horários. Para Tmax diária, o correto é pegar o
    TEMPERATURA MAXIMA NA HORA ANT. e tirar o máximo do dia.
    """
    with open(caminho, encoding="utf-8") as f:
        linhas = f.readlines()
    idx_cab = next((i for i, l in enumerate(linhas) if l.startswith("Data Medicao")), None)
    cabecalho = [c.strip() for c in linhas[idx_cab].strip().split(";")]
    idx = {nome: j for j, nome in enumerate(cabecalho)}

    col_data = idx["Data Medicao"]
    col_tmax_ant = idx["TEMPERATURA MAXIMA NA HORA ANT. (AUT)(°C)"]

    por_dia = defaultdict(list)
    for linha in linhas[idx_cab + 1:]:
        partes = [p.strip() for p in linha.strip().split(";")]
        if len(partes) <= max(col_data, col_tmax_ant):
            continue
        d = normalizar_data(partes[col_data])
        if not d:
            continue
        v = para_float(partes[col_tmax_ant])
        if v is not None:
            por_dia[d].append(v)

    return {d: max(vs) for d, vs in por_dia.items()}


def main():
    print("=" * 78)
    print(" TMAX — UFRA x INMET A201 (2018-2025)")
    print("=" * 78)

    ufra = carregar_ufra(DB_PATH)
    a201 = carregar_a201_diario(INMET_A201)
    print(f"\n UFRA: {len(ufra)} registros")
    print(f" A201: {len(a201)} registros")

    pares = []
    for d in sorted(set(ufra) & set(a201)):
        pares.append({"data": d, "ufra": ufra[d], "ref": a201[d],
                      "dif": ufra[d] - a201[d], "ano": int(d[:4])})

    print(f" Pareados: {len(pares)}")

    if not pares:
        print("\n Sem pares. Verifique o arquivo A201.")
        return

    difs = [p["dif"] for p in pares]
    xs = [p["ufra"] for p in pares]
    ys = [p["ref"] for p in pares]
    n = len(difs)

    media = sum(difs) / n
    mediana = statistics.median(difs)
    var = sum((d - media) ** 2 for d in difs) / n
    desvio = math.sqrt(var)
    rmse = math.sqrt(sum(d * d for d in difs) / n)
    ic = ic95(difs)
    r = pearson(xs, ys)
    d = willmott_d(xs, ys)
    pct = 100 * sum(1 for x in difs if x > 0) / n

    print(f"\n RESULTADO")
    print(f"   N:            {n}")
    print(f"   Média:        {media:+.3f} °C")
    print(f"   Mediana:      {mediana:+.3f} °C")
    print(f"   Desvio:       {desvio:.3f} °C")
    print(f"   RMSE:         {rmse:.3f} °C")
    print(f"   IC 95%:       [{ic[0]:+.3f}, {ic[1]:+.3f}]")
    print(f"   r:            {r:+.3f}" if r is not None else "")
    print(f"   Willmott d:   {d:+.3f}" if d is not None else "")
    print(f"   % UFRA > A201: {pct:.1f}%")

    # Por ano
    por_ano = defaultdict(list)
    for p in pares:
        por_ano[p["ano"]].append(p["dif"])

    print(f"\n VIÉS POR ANO")
    print(f" {'Ano':<6} {'N':>5} {'Média':>9} {'IC inf':>10} {'IC sup':>10}")
    print(" " + "-" * 45)
    res = []
    for ano in sorted(por_ano):
        difs_a = por_ano[ano]
        m = sum(difs_a) / len(difs_a)
        ic_a = ic95(difs_a)
        print(f" {ano:<6} {len(difs_a):>5} {m:>+9.3f} "
              f"{ic_a[0]:>+10.3f} {ic_a[1]:>+10.3f}")
        res.append({"ano": ano, "n": len(difs_a), "media": m,
                    "ic_inf": ic_a[0], "ic_sup": ic_a[1]})

    with open(SAIDA, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["ano", "n", "media", "ic_inf", "ic_sup"])
        w.writeheader()
        w.writerows(res)
    print(f"\n  {SAIDA}")

    print("\n" + "=" * 78)
    print(" FIM")
    print("=" * 78)


if __name__ == "__main__":
    main()