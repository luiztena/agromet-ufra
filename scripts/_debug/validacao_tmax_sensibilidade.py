"""
validacao_tmax_sensibilidade.py
-------------------------------
Validação da temperatura máxima diária (Tmax) da UFRA-BEL contra INMET 82191.

Replica a estrutura do diagnóstico de Tmin:
  - Sensibilidade a outliers (Opção B)
  - Sazonalidade (seca vs chuvosa)
  - Tendência temporal (por ano)
  - Comparação tripla (UFRA x 82191 x A201)

Saída:
  - validacao_tmax_resumo.csv
  - validacao_tmax_sazonalidade.csv
  - validacao_tmax_por_ano.csv
"""

import csv
import math
import sqlite3
import statistics
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# ---------------------------------------------------------------------------
# Configuração — CAMINHOS ABSOLUTOS
# ---------------------------------------------------------------------------
BASE_PROJETO = Path(r"C:\Users\luizt\Desktop\ISPAAM API\agromet-ufra")
DB_PATH          = BASE_PROJETO / "banco" / "ispaam.db"
INMET_D_82191    = BASE_PROJETO / "dados_82191_D_2018-01-01_2025-12-31.csv"

SAIDA_RESUMO     = BASE_PROJETO / "validacao_tmax_resumo.csv"
SAIDA_SAZONAL    = BASE_PROJETO / "validacao_tmax_sazonalidade.csv"
SAIDA_POR_ANO    = BASE_PROJETO / "validacao_tmax_por_ano.csv"

# Faixas plausíveis
FAIXA_TMAX_FISIO  = (25.0, 42.0)
FAIXA_TMAX_NORMAL = (29.0, 35.0)
FAIXA_TMAX_SUSP   = (20.0, 25.0)   # abaixo do normal, suspeito de erro

# Estações (Belém)
MESES_CHUVOSA = {12, 1, 2, 3, 4, 5}
MESES_SECA    = {6, 7, 8, 9, 10, 11}

NOMES_MES = {1:"Jan", 2:"Fev", 3:"Mar", 4:"Abr", 5:"Mai", 6:"Jun",
             7:"Jul", 8:"Ago", 9:"Set", 10:"Out", 11:"Nov", 12:"Dez"}


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
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
    den = sum((abs(obs[i] - media_obs) + abs(mod[i] - media_obs)) ** 2
              for i in range(n))
    if den == 0:
        return None
    return 1 - (num / den)


def t_pareado(difs):
    n = len(difs)
    if n < 2:
        return None, None
    media = sum(difs) / n
    var = sum((d - media) ** 2 for d in difs) / (n - 1)
    if var == 0:
        return None, None
    se = math.sqrt(var / n)
    t = media / se

    def erfc(x):
        z = abs(x)
        tt = 1.0 / (1.0 + 0.5 * z)
        ans = tt * math.exp(-z * z - 1.26551223 +
                            tt * (1.00002368 +
                            tt * (0.37409196 +
                            tt * (0.09678418 +
                            tt * (-0.18628806 +
                            tt * (0.27886807 +
                            tt * (-1.13520398 +
                            tt * (1.48851587 +
                            tt * (-0.82215223 +
                            tt * 0.17087277)))))))))
        return ans if x >= 0 else 2.0 - ans

    p = erfc(abs(t) / math.sqrt(2))
    return t, p


# ---------------------------------------------------------------------------
# Carregar UFRA
# ---------------------------------------------------------------------------
def carregar_ufra_tmax(caminho_db):
    con = sqlite3.connect(caminho_db)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    cur.execute("PRAGMA table_info(observacoes)")
    cols = {r[1] for r in cur.fetchall()}

    c_tmax = "tmax_real" if "tmax_real" in cols else "tmax"

    sql = f"""
        SELECT data_iso, {c_tmax} AS tmax
        FROM observacoes
        WHERE hora_local = '09:00'
        ORDER BY data_iso
    """

    ufra = {}
    for row in cur.execute(sql):
        data_iso = row["data_iso"]
        if not data_iso:
            continue
        v = para_float(row["tmax"])
        if v is not None:
            ufra[data_iso] = v
    con.close()
    return ufra


# ---------------------------------------------------------------------------
# Carregar INMET 82191
# ---------------------------------------------------------------------------
def carregar_inmet_diario(caminho):
    if not Path(caminho).exists():
        return {}
    with open(caminho, encoding="utf-8") as f:
        linhas = f.readlines()

    idx_cab = next((i for i, l in enumerate(linhas) if l.startswith("Data Medicao")), None)
    if idx_cab is None:
        return {}

    cabecalho = [c.strip() for c in linhas[idx_cab].strip().split(";")]
    idx = {nome: j for j, nome in enumerate(cabecalho)}

    col_data = idx["Data Medicao"]
    col_tmax = idx["TEMPERATURA MAXIMA, DIARIA(°C)"]

    inmet = {}
    for linha in linhas[idx_cab + 1:]:
        partes = [p.strip() for p in linha.strip().split(";")]
        if len(partes) <= max(col_data, col_tmax):
            continue
        data = normalizar_data(partes[col_data])
        if not data:
            continue
        v = para_float(partes[col_tmax])
        if v is not None:
            inmet[data] = v
    return inmet


# ---------------------------------------------------------------------------
# Pareamento
# ---------------------------------------------------------------------------
def parear(ufra, inmet):
    pares = []
    for data in sorted(set(ufra) & set(inmet)):
        u = ufra[data]
        i = inmet[data]
        dif = u - i
        ano = int(data[:4])
        mes = int(data[5:7])
        estacao = "chuvosa" if mes in MESES_CHUVOSA else "seca"

        # Flags
        fora_fisio = not (FAIXA_TMAX_FISIO[0] <= u <= FAIXA_TMAX_FISIO[1])
        suspeito   = FAIXA_TMAX_SUSP[0] <= u <= FAIXA_TMAX_SUSP[1]

        pares.append({
            "data": data, "ano": ano, "mes": mes, "estacao": estacao,
            "ufra": u, "inmet": i, "dif": dif,
            "fora_fisio": fora_fisio, "suspeito": suspeito,
        })
    return pares


# ---------------------------------------------------------------------------
# Métricas por cenário
# ---------------------------------------------------------------------------
def metricas(pares, nome):
    if not pares:
        return None
    difs = [p["dif"] for p in pares]
    xs = [p["ufra"] for p in pares]
    ys = [p["inmet"] for p in pares]
    n = len(difs)

    media   = sum(difs) / n
    mediana = statistics.median(difs)
    var     = sum((d - media) ** 2 for d in difs) / n
    desvio  = math.sqrt(var)
    rmse    = math.sqrt(sum(d * d for d in difs) / n)
    ic      = ic95(difs)
    r       = pearson(xs, ys)
    d       = willmott_d(xs, ys)
    t, p    = t_pareado(difs)

    return {
        "cenario": nome, "n": n, "media": media, "mediana": mediana,
        "desvio": desvio, "rmse": rmse,
        "ic_inf": ic[0], "ic_sup": ic[1],
        "r": r, "d": d, "p_valor": p,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 78)
    print(" VALIDAÇÃO DE TMAX — UFRA-BEL × INMET 82191")
    print("=" * 78)

    print("\n[1/3] Carregando UFRA...")
    ufra = carregar_ufra_tmax(DB_PATH)
    print(f"      {len(ufra)} registros com Tmax válido")

    print("[2/3] Carregando INMET 82191...")
    inmet = carregar_inmet_diario(INMET_D_82191)
    print(f"      {len(inmet)} registros")

    print("[3/3] Pareando...")
    pares = parear(ufra, inmet)
    print(f"      {len(pares)} pares válidos")

    if not pares:
        print("\nERRO: nenhum par válido. Verifique os caminhos.")
        return

    # Distribuição
    n_fora = sum(1 for p in pares if p["fora_fisio"])
    n_susp = sum(1 for p in pares if p["suspeito"])
    print(f"\n Distribuição:")
    print(f"   fora da faixa fisiológica: {n_fora}")
    print(f"   suspeito (< 25 °C):         {n_susp}")

    # Cenários
    cenarios = [
        ("C0 - completo",          lambda p: True),
        ("C1 - sem fora_fisio",    lambda p: not p["fora_fisio"]),
        ("C2 - sem suspeito",      lambda p: not p["suspeito"]),
        ("C3 - 2018-2022",         lambda p: 2018 <= p["ano"] <= 2022),
        ("C4 - 2023-2025",         lambda p: 2023 <= p["ano"] <= 2025),
        ("C5 - 2018-2025 limpo",   lambda p: not p["fora_fisio"] and not p["suspeito"]),
    ]

    print("\n" + "=" * 78)
    print(" RESULTADOS POR CENÁRIO")
    print("=" * 78)

    resultados = []
    for nome, filtro in cenarios:
        sub = [p for p in pares if filtro(p)]
        m = metricas(sub, nome)
        if m is None:
            print(f"\n {nome}: sem dados")
            continue
        print(f"\n {nome}")
        print(f"   N:            {m['n']:5d}")
        print(f"   Média:        {m['media']:+.3f} °C")
        print(f"   Mediana:      {m['mediana']:+.3f} °C")
        print(f"   Desvio:       {m['desvio']:.3f} °C")
        print(f"   RMSE:         {m['rmse']:.3f} °C")
        print(f"   IC 95%:       [{m['ic_inf']:+.3f}, {m['ic_sup']:+.3f}]")
        if m["r"] is not None:
            print(f"   r:            {m['r']:+.3f}")
        if m["d"] is not None:
            print(f"   Willmott d:   {m['d']:+.3f}")
        if m["p_valor"] is not None:
            print(f"   p-valor:      {m['p_valor']:.3e}")
        resultados.append(m)

    # Por estação
    print("\n" + "=" * 78)
    print(" SAZONALIDADE (seca vs chuvosa)")
    print("=" * 78)

    difs_chuvosa = [p["dif"] for p in pares if p["estacao"] == "chuvosa"]
    difs_seca    = [p["dif"] for p in pares if p["estacao"] == "seca"]

    res_saz = []
    for nome, difs in [("chuvosa", difs_chuvosa), ("seca", difs_seca)]:
        if not difs:
            continue
        n = len(difs)
        media = sum(difs) / n
        mediana = statistics.median(difs)
        var = sum((d - media) ** 2 for d in difs) / n
        desvio = math.sqrt(var)
        ic = ic95(difs)
        pct_ufra_maior = 100 * sum(1 for d in difs if d > 0) / n

        print(f"\n {nome.upper()}")
        print(f"   N:              {n}")
        print(f"   Média:          {media:+.3f} °C")
        print(f"   Mediana:        {mediana:+.3f} °C")
        print(f"   IC 95%:         [{ic[0]:+.3f}, {ic[1]:+.3f}]")
        print(f"   % UFRA > INMET: {pct_ufra_maior:.1f}%")

        res_saz.append({
            "estacao": nome, "n": n, "media": media, "mediana": mediana,
            "desvio": desvio, "ic_inf": ic[0], "ic_sup": ic[1],
            "pct_ufra_maior": pct_ufra_maior,
        })

    if len(res_saz) == 2:
        dif = res_saz[1]["media"] - res_saz[0]["media"]
        print(f"\n   Diferença (seca - chuvosa): {dif:+.3f} °C")

    # Por ano
    print("\n" + "=" * 78)
    print(" VIÉS POR ANO")
    print("=" * 78)

    por_ano = defaultdict(list)
    for p in pares:
        por_ano[p["ano"]].append(p["dif"])

    print(f"\n {'Ano':<6} {'N':>6} {'Média':>10} {'Mediana':>10} "
          f"{'IC inf':>10} {'IC sup':>10}")
    print(" " + "-" * 60)

    res_ano = []
    for ano in sorted(por_ano):
        difs = por_ano[ano]
        n = len(difs)
        media = sum(difs) / n
        mediana = statistics.median(difs)
        ic = ic95(difs)
        print(f" {ano:<6} {n:>6} {media:>+10.3f} {mediana:>+10.3f} "
              f"{ic[0]:>+10.3f} {ic[1]:>+10.3f}")
        res_ano.append({
            "ano": ano, "n": n, "media": media, "mediana": mediana,
            "ic_inf": ic[0], "ic_sup": ic[1],
        })

    # Exportar
    print("\n" + "=" * 78)
    print(" EXPORTANDO CSVs")
    print("=" * 78)

    with open(SAIDA_RESUMO, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["cenario", "n", "media", "mediana", "desvio", "rmse",
                    "ic_inf", "ic_sup", "r", "d", "p_valor"])
        for m in resultados:
            w.writerow([m["cenario"], m["n"], f"{m['media']:.4f}",
                        f"{m['mediana']:.4f}", f"{m['desvio']:.4f}",
                        f"{m['rmse']:.4f}", f"{m['ic_inf']:.4f}",
                        f"{m['ic_sup']:.4f}",
                        f"{m['r']:.4f}" if m["r"] else "",
                        f"{m['d']:.4f}" if m["d"] else "",
                        f"{m['p_valor']:.4e}" if m["p_valor"] else ""])
    print(f"  {SAIDA_RESUMO}")

    with open(SAIDA_SAZONAL, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["estacao", "n", "media", "mediana", "desvio",
                    "ic_inf", "ic_sup", "pct_ufra_maior"])
        for r in res_saz:
            w.writerow([r["estacao"], r["n"], f"{r['media']:.4f}",
                        f"{r['mediana']:.4f}", f"{r['desvio']:.4f}",
                        f"{r['ic_inf']:.4f}", f"{r['ic_sup']:.4f}",
                        f"{r['pct_ufra_maior']:.2f}"])
    print(f"  {SAIDA_SAZONAL}")

    with open(SAIDA_POR_ANO, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ano", "n", "media", "mediana", "ic_inf", "ic_sup"])
        for r in res_ano:
            w.writerow([r["ano"], r["n"], f"{r['media']:.4f}",
                        f"{r['mediana']:.4f}", f"{r['ic_inf']:.4f}",
                        f"{r['ic_sup']:.4f}"])
    print(f"  {SAIDA_POR_ANO}")

    print("\n" + "=" * 78)
    print(" FIM")
    print("=" * 78)


if __name__ == "__main__":
    main()