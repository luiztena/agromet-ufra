"""
validacao_tmax_sazonalidade_mensal.py
-------------------------------------
Viés de Tmax UFRA x INMET 82191 por mês, 2018-2025.
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

SAIDA_MENSAL = BASE / "validacao_tmax_sazonalidade_mensal.csv"
SAIDA_ESTACOES = BASE / "validacao_tmax_sazonalidade_estacoes.csv"

MESES_CHUVOSA = {12, 1, 2, 3, 4, 5}
MESES_SECA = {6, 7, 8, 9, 10, 11}
NOMES_MES = {1:"Jan", 2:"Fev", 3:"Mar", 4:"Abr", 5:"Mai", 6:"Jun",
             7:"Jul", 8:"Ago", 9:"Set", 10:"Out", 11:"Nov", 12:"Dez"}


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
    print(" VIÉS DE TMAX POR MÊS — UFRA x INMET 82191 (2018-2025)")
    print("=" * 78)

    ufra = carregar_ufra(DB_PATH)
    inmet = carregar_inmet(INMET_D_82191)
    print(f"\n UFRA: {len(ufra)} registros")
    print(f" INMET: {len(inmet)} registros")

    pares = []
    for d in sorted(set(ufra) & set(inmet)):
        mes = int(d[5:7])
        estacao = "chuvosa" if mes in MESES_CHUVOSA else "seca"
        pares.append({
            "data": d, "ano": int(d[:4]), "mes": mes, "estacao": estacao,
            "dif": ufra[d] - inmet[d],
        })
    print(f" Pareados: {len(pares)}")

    # Por mês
    por_mes = defaultdict(list)
    for p in pares:
        por_mes[p["mes"]].append(p["dif"])

    print("\n" + "=" * 78)
    print(" VIÉS POR MÊS")
    print("=" * 78)
    print(f"\n {'Mês':<5} {'N':>5} {'Média':>9} {'Mediana':>9} {'Desvio':>8} "
          f"{'IC inf':>10} {'IC sup':>10} {'%U>I':>6} {'Estação':>9}")
    print(" " + "-" * 78)

    res_mes = []
    for mes in range(1, 13):
        difs = por_mes.get(mes, [])
        if not difs:
            continue
        n = len(difs)
        media = sum(difs) / n
        mediana = statistics.median(difs)
        var = sum((d - media) ** 2 for d in difs) / n
        desvio = math.sqrt(var)
        ic = ic95(difs)
        pct = 100 * sum(1 for d in difs if d > 0) / n
        estacao = "chuvosa" if mes in MESES_CHUVOSA else "seca"
        print(f" {NOMES_MES[mes]:<5} {n:>5} {media:>+9.3f} {mediana:>+9.3f} "
              f"{desvio:>8.3f} {ic[0]:>+10.3f} {ic[1]:>+10.3f} "
              f"{pct:>5.1f}% {estacao:>9}")
        res_mes.append({
            "mes": mes, "nome": NOMES_MES[mes], "n": n, "media": media,
            "mediana": mediana, "desvio": desvio,
            "ic_inf": ic[0], "ic_sup": ic[1],
            "pct_ufra_maior": pct, "estacao": estacao,
        })

    # Por estação
    print("\n" + "=" * 78)
    print(" AGRUPADO POR ESTAÇÃO")
    print("=" * 78)

    difs_chuvosa = [p["dif"] for p in pares if p["estacao"] == "chuvosa"]
    difs_seca = [p["dif"] for p in pares if p["estacao"] == "seca"]

    res_est = []
    for nome, difs in [("chuvosa", difs_chuvosa), ("seca", difs_seca)]:
        n = len(difs)
        media = sum(difs) / n
        mediana = statistics.median(difs)
        var = sum((d - media) ** 2 for d in difs) / n
        desvio = math.sqrt(var)
        ic = ic95(difs)
        pct = 100 * sum(1 for d in difs if d > 0) / n
        print(f"\n {nome.upper()}")
        print(f"   N:              {n}")
        print(f"   Média:          {media:+.3f} °C")
        print(f"   Mediana:        {mediana:+.3f} °C")
        print(f"   IC 95%:         [{ic[0]:+.3f}, {ic[1]:+.3f}]")
        print(f"   % UFRA > INMET: {pct:.1f}%")
        res_est.append({
            "estacao": nome, "n": n, "media": media, "mediana": mediana,
            "desvio": desvio, "ic_inf": ic[0], "ic_sup": ic[1],
            "pct_ufra_maior": pct,
        })

    if len(res_est) == 2:
        dif = res_est[1]["media"] - res_est[0]["media"]
        print(f"\n   Diferença (seca - chuvosa): {dif:+.3f} °C")

    # Exportar
    with open(SAIDA_MENSAL, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["mes", "nome", "n", "media",
                                          "mediana", "desvio",
                                          "ic_inf", "ic_sup",
                                          "pct_ufra_maior", "estacao"])
        w.writeheader()
        w.writerows(res_mes)
    print(f"\n  {SAIDA_MENSAL}")

    with open(SAIDA_ESTACOES, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["estacao", "n", "media", "mediana",
                                          "desvio", "ic_inf", "ic_sup",
                                          "pct_ufra_maior"])
        w.writeheader()
        w.writerows(res_est)
    print(f"  {SAIDA_ESTACOES}")

    print("\n" + "=" * 78)
    print(" FIM")
    print("=" * 78)


if __name__ == "__main__":
    main()