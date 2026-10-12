"""
diagnostico_tmin_sazonalidade.py
--------------------------------
Viés de Tmin UFRA × INMET 82191 por mês, período 2018-2022.

Objetivo: testar se o viés é maior na estação seca (jun-nov), quando a
radiação noturna é máxima e o sítio físico da UFRA (grama + árvores + rio)
produz resfriamento mais intenso.

Se confirmar, fecha o diagnóstico: viés real, físico, sazonal.

Saída:
  - tmin_sazonalidade_mensal.csv
  - tmin_sazonalidade_estacoes.csv
  - tmin_sazonalidade_por_ano.csv
"""

import csv
import math
import sqlite3
import statistics
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
BASE = Path(__file__).resolve().parent.parent.parent
DB_PATH       = BASE / "banco" / "ispaam.db"
INMET_D_82191 = BASE / "dados_82191_D_2018-01-01_2025-12-31.csv"

SAIDA_MENSAL    = BASE / "tmin_sazonalidade_mensal.csv"
SAIDA_ESTACOES  = BASE / "tmin_sazonalidade_estacoes.csv"
SAIDA_POR_ANO   = BASE / "tmin_sazonalidade_por_ano.csv"

# Período limpo (antes da quebra estrutural de julho/2023)
ANO_INICIO = 2018
ANO_FIM    = 2022

# Definição de estações (Belém)
# Chuvosa: dezembro a maio
# Seca:    junho a novembro
MESES_CHUVOSA = {12, 1, 2, 3, 4, 5}
MESES_SECA    = {6, 7, 8, 9, 10, 11}

NOMES_MES = {
    1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Set", 10: "Out", 11: "Nov", 12: "Dez",
}


# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------
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


def t_pareado(difs):
    """t e p-valor bicaudal aproximado (normal)."""
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


def mann_whitney_u_aprox(xs, ys):
    """
    Teste de Mann-Whitney U aproximado pela normal, sem scipy.
    Retorna U, z, p-valor bicaudal.
    """
    n1, n2 = len(xs), len(ys)
    if n1 < 2 or n2 < 2:
        return None, None, None
    combinado = [(v, 0) for v in xs] + [(v, 1) for v in ys]
    combinado.sort(key=lambda x: x[0])
    # ranks com empates
    ranks = [0.0] * len(combinado)
    i = 0
    while i < len(combinado):
        j = i
        while j + 1 < len(combinado) and combinado[j + 1][0] == combinado[i][0]:
            j += 1
        rank_medio = (i + j) / 2.0 + 1
        for k in range(i, j + 1):
            ranks[k] = rank_medio
        i = j + 1

    rank_soma_x = sum(ranks[k] for k in range(len(combinado)) if combinado[k][1] == 0)
    u1 = rank_soma_x - n1 * (n1 + 1) / 2.0
    u2 = n1 * n2 - u1
    u = min(u1, u2)

    media_u = n1 * n2 / 2.0
    # variância com correção de empates (simplificada)
    desvio_u = math.sqrt(n1 * n2 * (n1 + n2 + 1) / 12.0)

    if desvio_u == 0:
        return u, None, None
    z = (u - media_u) / desvio_u

    def erfc(x):
        zz = abs(x)
        tt = 1.0 / (1.0 + 0.5 * zz)
        ans = tt * math.exp(-zz * zz - 1.26551223 +
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

    p = erfc(abs(z) / math.sqrt(2))
    return u, z, p


# ---------------------------------------------------------------------------
# Carregar dados
# ---------------------------------------------------------------------------
def carregar_ufra_diario(caminho_db):
    con = sqlite3.connect(caminho_db)
    cur = con.cursor()
    cur.execute("""
        SELECT data_iso, tmin, tmin_real
        FROM observacoes
        WHERE hora_local = '09:00'
        ORDER BY data_iso
    """)
    ufra = {}
    for data, tmin, tmin_real in cur:
        if data is None:
            continue
        v = para_float(tmin)
        if v is None:
            v = para_float(tmin_real)
        if v is not None:
            ufra[data] = v
    con.close()
    return ufra


def carregar_inmet_diario(caminho):
    with open(caminho, encoding="utf-8") as f:
        linhas = f.readlines()

    idx_cab = next((i for i, l in enumerate(linhas) if l.startswith("Data Medicao")), None)
    cabecalho = [c.strip() for c in linhas[idx_cab].strip().split(";")]
    idx = {nome: j for j, nome in enumerate(cabecalho)}

    col_data = idx["Data Medicao"]
    col_tmin = idx["TEMPERATURA MINIMA, DIARIA(°C)"]

    inmet = {}
    for linha in linhas[idx_cab + 1:]:
        partes = [p.strip() for p in linha.strip().split(";")]
        if len(partes) <= max(col_data, col_tmin):
            continue
        data = normalizar_data(partes[col_data])
        if not data:
            continue
        v = para_float(partes[col_tmin])
        if v is not None:
            inmet[data] = v
    return inmet


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 78)
    print(f" VIÉS DE Tmin POR MÊS — UFRA × INMET 82191 — {ANO_INICIO}-{ANO_FIM}")
    print("=" * 78)

    print("\n[1/4] Carregando UFRA...")
    ufra = carregar_ufra_diario(DB_PATH)
    print(f"      {len(ufra)} registros com tmin não-nulo")

    print("[2/4] Carregando INMET 82191...")
    inmet = carregar_inmet_diario(INMET_D_82191)
    print(f"      {len(inmet)} registros")

    print("[3/4] Pareando e filtrando período...")
    pares = []
    for data in sorted(set(ufra) & set(inmet)):
        ano = int(data[:4])
        if not (ANO_INICIO <= ano <= ANO_FIM):
            continue
        u = ufra[data]
        i = inmet[data]
        pares.append({
            "data": data,
            "ano": ano,
            "mes": int(data[5:7]),
            "ufra": u,
            "inmet": i,
            "dif": u - i,
        })
    print(f"      {len(pares)} pares válidos em {ANO_INICIO}-{ANO_FIM}")

    # -----------------------------------------------------------------------
    # 1. Viés por mês
    # -----------------------------------------------------------------------
    print("\n[4/4] Calculando viés por mês...")
    por_mes = defaultdict(list)
    for p in pares:
        por_mes[p["mes"]].append(p["dif"])

    print("\n" + "=" * 78)
    print(" VIÉS POR MÊS")
    print("=" * 78)
    print(f"\n {'Mês':<5} {'N':>5} {'Média':>9} {'Mediana':>9} {'Desvio':>8} "
          f"{'IC 95% inf':>11} {'IC 95% sup':>11} {'%U<I':>6} {'Estação':>9}")
    print(" " + "-" * 78)

    resultados_mes = []
    for mes in range(1, 13):
        difs = por_mes.get(mes, [])
        if not difs:
            print(f" {NOMES_MES[mes]:<5} {'—':>5}")
            continue
        n = len(difs)
        media = sum(difs) / n
        mediana = statistics.median(difs)
        var = sum((d - media) ** 2 for d in difs) / n
        desvio = math.sqrt(var)
        ic_inf, ic_sup = ic95(difs)
        pct_menor = 100 * sum(1 for d in difs if d < 0) / n
        estacao = "chuvosa" if mes in MESES_CHUVOSA else "seca"

        print(f" {NOMES_MES[mes]:<5} {n:>5} {media:>+9.3f} {mediana:>+9.3f} "
              f"{desvio:>8.3f} {ic_inf:>+11.3f} {ic_sup:>+11.3f} "
              f"{pct_menor:>5.1f}% {estacao:>9}")

        resultados_mes.append({
            "mes": mes,
            "nome": NOMES_MES[mes],
            "n": n,
            "media": media,
            "mediana": mediana,
            "desvio": desvio,
            "ic_inf": ic_inf,
            "ic_sup": ic_sup,
            "pct_ufra_menor": pct_menor,
            "estacao": estacao,
        })

    # -----------------------------------------------------------------------
    # 2. Agrupamento por estação
    # -----------------------------------------------------------------------
    print("\n" + "=" * 78)
    print(" VIÉS POR ESTAÇÃO (chuvosa: dez-mai | seca: jun-nov)")
    print("=" * 78)

    difs_chuvosa = [p["dif"] for p in pares if p["mes"] in MESES_CHUVOSA]
    difs_seca    = [p["dif"] for p in pares if p["mes"] in MESES_SECA]

    def resumo_estacao(nome, difs):
        n = len(difs)
        if n == 0:
            return None
        media = sum(difs) / n
        mediana = statistics.median(difs)
        var = sum((d - media) ** 2 for d in difs) / n
        desvio = math.sqrt(var)
        ic_inf, ic_sup = ic95(difs)
        pct_menor = 100 * sum(1 for d in difs if d < 0) / n
        t, p = t_pareado(difs)
        return {
            "estacao": nome,
            "n": n,
            "media": media,
            "mediana": mediana,
            "desvio": desvio,
            "ic_inf": ic_inf,
            "ic_sup": ic_sup,
            "pct_ufra_menor": pct_menor,
            "t": t,
            "p_valor": p,
        }

    res_chuvosa = resumo_estacao("chuvosa", difs_chuvosa)
    res_seca    = resumo_estacao("seca", difs_seca)

    for r in [res_chuvosa, res_seca]:
        print(f"\n {r['estacao'].upper()}")
        print(f"   N:              {r['n']}")
        print(f"   Média:          {r['media']:+.3f} °C")
        print(f"   Mediana:        {r['mediana']:+.3f} °C")
        print(f"   Desvio:         {r['desvio']:.3f} °C")
        print(f"   IC 95%:         [{r['ic_inf']:+.3f}, {r['ic_sup']:+.3f}]")
        print(f"   % UFRA < INMET: {r['pct_ufra_menor']:.1f}%")
        print(f"   p-valor (viés≠0): {r['p_valor']:.3e}")

    # -----------------------------------------------------------------------
    # 3. Teste de diferença entre estações
    # -----------------------------------------------------------------------
    print("\n" + "=" * 78)
    print(" TESTE: viés da seca vs viés da chuvosa")
    print("=" * 78)

    dif_medias = res_seca["media"] - res_chuvosa["media"]
    print(f"\n   Diferença de médias (seca - chuvosa): {dif_medias:+.3f} °C")

    # Teste t de Welch (aproximado)
    n1, n2 = res_seca["n"], res_chuvosa["n"]
    m1, m2 = res_seca["media"], res_chuvosa["media"]
    s1, s2 = res_seca["desvio"], res_chuvosa["desvio"]
    se = math.sqrt(s1**2/n1 + s2**2/n2)
    if se > 0:
        t_welch = (m1 - m2) / se
        def erfc(x):
            zz = abs(x)
            tt = 1.0 / (1.0 + 0.5 * zz)
            ans = tt * math.exp(-zz * zz - 1.26551223 +
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
        p_welch = erfc(abs(t_welch) / math.sqrt(2))
        print(f"   t de Welch: {t_welch:+.3f}")
        print(f"   p-valor:    {p_welch:.3e}")
        if p_welch < 0.05:
            print("   >> Diferença ESTATISTICAMENTE SIGNIFICATIVA (p < 0,05)")
        else:
            print("   >> Diferença NÃO significativa (p >= 0,05)")

    # Mann-Whitney U
    u, z, p_u = mann_whitney_u_aprox(difs_seca, difs_chuvosa)
    if u is not None:
        print(f"\n   Mann-Whitney U: {u:.0f}")
        print(f"   z:              {z:+.3f}")
        print(f"   p-valor:        {p_u:.3e}")
        if p_u < 0.05:
            print("   >> Distribuições DIFERENTES entre as estações (p < 0,05)")
        else:
            print("   >> Distribuições NÃO distinguíveis (p >= 0,05)")

    # -----------------------------------------------------------------------
    # 4. Viés por ano (verificar estabilidade temporal)
    # -----------------------------------------------------------------------
    print("\n" + "=" * 78)
    print(" VIÉS POR ANO (estabilidade temporal)")
    print("=" * 78)
    print(f"\n {'Ano':<5} {'N':>5} {'Média':>9} {'Mediana':>9} {'IC 95% inf':>11} {'IC 95% sup':>11}")
    print(" " + "-" * 60)

    resultados_ano = []
    por_ano = defaultdict(list)
    for p in pares:
        por_ano[p["ano"]].append(p["dif"])

    for ano in sorted(por_ano):
        difs = por_ano[ano]
        n = len(difs)
        media = sum(difs) / n
        mediana = statistics.median(difs)
        ic_inf, ic_sup = ic95(difs)
        print(f" {ano:<5} {n:>5} {media:>+9.3f} {mediana:>+9.3f} "
              f"{ic_inf:>+11.3f} {ic_sup:>+11.3f}")
        resultados_ano.append({
            "ano": ano, "n": n, "media": media, "mediana": mediana,
            "ic_inf": ic_inf, "ic_sup": ic_sup,
        })

    # -----------------------------------------------------------------------
    # 5. Exportar
    # -----------------------------------------------------------------------
    print("\n" + "=" * 78)
    print(" EXPORTANDO CSVs")
    print("=" * 78)

    with open(SAIDA_MENSAL, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["mes", "nome", "n", "media",
                                          "mediana", "desvio",
                                          "ic_inf", "ic_sup",
                                          "pct_ufra_menor", "estacao"])
        w.writeheader()
        for r in resultados_mes:
            w.writerow(r)
    print(f"  {SAIDA_MENSAL}")

    with open(SAIDA_ESTACOES, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["estacao", "n", "media", "mediana",
                                          "desvio", "ic_inf", "ic_sup",
                                          "pct_ufra_menor", "t", "p_valor"])
        w.writeheader()
        for r in [res_chuvosa, res_seca]:
            w.writerow(r)
    print(f"  {SAIDA_ESTACOES}")

    with open(SAIDA_POR_ANO, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["ano", "n", "media", "mediana",
                                          "ic_inf", "ic_sup"])
        w.writeheader()
        for r in resultados_ano:
            w.writerow(r)
    print(f"  {SAIDA_POR_ANO}")

    # -----------------------------------------------------------------------
    # 6. Leitura automática
    # -----------------------------------------------------------------------
    print("\n" + "=" * 78)
    print(" LEITURA AUTOMÁTICA")
    print("=" * 78)

    media_chuvosa = res_chuvosa["media"]
    media_seca    = res_seca["media"]

    print(f"\n  Viés médio na estação CHUVOSA:  {media_chuvosa:+.3f} °C")
    print(f"  Viés médio na estação SECA:     {media_seca:+.3f} °C")
    print(f"  Diferença (seca - chuvosa):     {media_seca - media_chuvosa:+.3f} °C")

    if media_seca < media_chuvosa - 0.2:
        print("\n  >> CONFIRMADO: viés maior em módulo na estação seca.")
        print("  >> Consistente com hipótese física do sítio (radiação noturna")
        print("     mais intensa + inversão térmica mais forte em jun-nov).")
    elif media_seca < media_chuvosa:
        print("\n  >> PARCIAL: viés ligeiramente maior na seca, mas < 0,2 °C.")
        print("  >> Sinal físico presente, mas fraco.")
    else:
        print("\n  >> NÃO CONFIRMADO: viés não é maior na seca.")
        print("  >> Hipótese física do sítio precisa de reavaliação.")

    print("\n" + "=" * 78)
    print(" FIM")
    print("=" * 78)


if __name__ == "__main__":
    main()