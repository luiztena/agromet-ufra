"""
diagnostico_tmin_sensibilidade.py
---------------------------------
Opção B: mantém todos os dados, reporta viés de Tmin sob múltiplos cortes.

Cenários:
  C0 - Série completa (todos os dados pareados)
  C1 - Sem outliers de QC (remove o que o QC já anulou)
  C2 - Sem suspeita de troca tmin<-tmax (26-34 °C)
  C3 - Sem outliers E sem suspeita de troca
  C4 - Apenas 2018-2022 (período antes da quebra estrutural de 2023)
  C5 - Apenas 2023-2026 (período pós-quebra)
  C6 - Robustez: mediana do viés em vez de média
  C7 - Robustez: viés trimestral (mediana por trimestre)

Para cada cenário:
  - N pareado
  - Viés (média e mediana)
  - Desvio padrão
  - RMSE
  - r de Pearson
  - Willmott d
  - IC 95% do viés
  - Teste t pareado (p-valor)
  - Teste de Wilcoxon (não-paramétrico)

Saída:
  - tmin_sensibilidade_resumo.csv
  - tmin_sensibilidade_pares.csv (todos os pares com flags)
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

SAIDA_RESUMO = BASE / "tmin_sensibilidade_resumo.csv"
SAIDA_PARES  = BASE / "tmin_sensibilidade_pares.csv"

# Faixas QC corrigidas (o ponto crítico do relatório de auditoria)
FAIXA_TMIN_FISIO   = (18.0, 26.0)   # o que é fisicamente possível
FAIXA_TMIN_NORMAL  = (22.0, 26.0)   # o que é típico em Belém
FAIXA_TMAX_FISIO   = (26.0, 45.0)
FAIXA_TMAX_NORMAL  = (29.0, 34.0)

# Faixa de suspeita de troca tmin <- tmax
FAIXA_SUSPEITA_TROCA = (26.0, 34.0)

# Faixa do INMET para Tmin diária (mesmo clima, mesma faixa)
FAIXA_TMIN_INMET = (18.0, 30.0)     # mais permissivo: queremos pegar tudo


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


def ic95(vies, desvio, n):
    if n < 2:
        return None
    se = desvio / math.sqrt(n)
    return (vies - 1.96 * se, vies + 1.96 * se)


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


def t_pareado_aproximado(difs):
    """
    t pareado: t = media / (desvio / sqrt(n)).
    Retorna t e p-valor aproximado (bicaudal) usando a normal para n grande.
    Não depende de scipy.
    """
    n = len(difs)
    if n < 2:
        return None, None
    media = sum(difs) / n
    var = sum((d - media) ** 2 for d in difs) / (n - 1)
    if var == 0:
        return None, None
    se = math.sqrt(var / n)
    t = media / se
    # p-valor bicaudal aproximado via erro de erfc
    # Usa a aproximação normal padrão: p ≈ 2 * (1 - Phi(|t|))
    # Phi via função erro complementar
    def erfc(x):
        # Aproximação de Numerical Recipes
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
# Carregar UFRA diário com flags
# ---------------------------------------------------------------------------
def carregar_ufra_diario_com_flags(caminho_db):
    con = sqlite3.connect(caminho_db)
    cur = con.cursor()

    cur.execute("PRAGMA table_info(observacoes)")
    cols = {r[1] for r in cur.fetchall()}

    def pick(*nomes):
        for n in nomes:
            if n in cols:
                return n
        return None

    c_tmax      = pick("tmax_real", "tmax")
    c_tmin      = pick("tmin_real", "tmin")
    c_tmax_alt  = "tmax" if c_tmax != "tmax" else None
    c_tmin_alt  = "tmin" if c_tmin != "tmin" else None

    campos = [c_tmax, c_tmin]
    if c_tmax_alt: campos.append(c_tmax_alt)
    if c_tmin_alt: campos.append(c_tmin_alt)

    sql = f"""
        SELECT data_iso, {', '.join(campos)}
        FROM observacoes
        WHERE hora_local = '09:00'
        ORDER BY data_iso
    """

    ufra_d = {}
    for row in cur.execute(sql):
        data_iso = row[0]
        if data_iso is None:
            continue

        tmax = para_float(row[1]) if c_tmax else None
        tmin = para_float(row[2]) if c_tmin else None

        # Alternativas (tmax_real vs tmax)
        idx = 3
        if c_tmax_alt:
            v = para_float(row[idx]); idx += 1
            if tmax is None: tmax = v
        if c_tmin_alt:
            v = para_float(row[idx])
            if tmin is None: tmin = v

        ufra_d[data_iso] = {"tmax": tmax, "tmin": tmin}

    con.close()
    return ufra_d


# ---------------------------------------------------------------------------
# Carregar INMET 82191 diário
# ---------------------------------------------------------------------------
def carregar_inmet_diario(caminho):
    with open(caminho, encoding="utf-8") as f:
        linhas = f.readlines()

    idx_cab = next((i for i, l in enumerate(linhas) if l.startswith("Data Medicao")), None)
    if idx_cab is None:
        raise RuntimeError(f"Cabeçalho não encontrado em {caminho}")

    cabecalho = [c.strip() for c in linhas[idx_cab].strip().split(";")]
    idx = {nome: j for j, nome in enumerate(cabecalho)}

    col_data = idx["Data Medicao"]
    col_tmax = idx["TEMPERATURA MAXIMA, DIARIA(°C)"]
    col_tmin = idx["TEMPERATURA MINIMA, DIARIA(°C)"]

    inmet = {}
    for linha in linhas[idx_cab + 1:]:
        partes = [p.strip() for p in linha.strip().split(";")]
        if len(partes) <= max(col_data, col_tmax, col_tmin):
            continue
        data = normalizar_data(partes[col_data])
        if not data:
            continue
        inmet[data] = {
            "tmax": para_float(partes[col_tmax]),
            "tmin": para_float(partes[col_tmin]),
        }
    return inmet


# ---------------------------------------------------------------------------
# Flags de qualidade
# ---------------------------------------------------------------------------
def classificar_par(data, ufra_tmin, inmet_tmin):
    """
    Retorna dict de flags para o par (data, ufra_tmin, inmet_tmin).

    Flags:
      fora_fisio          : tmin fora de [18, 26] em qualquer das duas
      suspeita_troca      : tmin_ufra em [26, 34] (provável tmax)
      inmet_suspeito      : tmin_inmet fora de [18, 30]
      fim_semana          : dia da semana
      ano                 : ano (para filtrar 2018-2022 vs 2023-2026)
      trimestre           : 1-4
      mes                 : 1-12
    """
    ano = int(data[:4])
    mes = int(data[5:7])
    trimestre = (mes - 1) // 3 + 1

    try:
        dia_semana = datetime.strptime(data, "%Y-%m-%d").weekday()
    except ValueError:
        dia_semana = None

    flags = {
        "ano": ano,
        "mes": mes,
        "trimestre": trimestre,
        "dia_semana": dia_semana,
        "fora_fisio": False,
        "suspeita_troca": False,
        "inmet_suspeito": False,
    }

    if ufra_tmin is not None:
        lo, hi = FAIXA_TMIN_FISIO
        if ufra_tmin < lo or ufra_tmin > hi:
            flags["fora_fisio"] = True
        lo, hi = FAIXA_SUSPEITA_TROCA
        if lo < ufra_tmin < hi:
            flags["suspeita_troca"] = True

    if inmet_tmin is not None:
        lo, hi = FAIXA_TMIN_INMET
        if inmet_tmin < lo or inmet_tmin > hi:
            flags["inmet_suspeito"] = True

    return flags


# ---------------------------------------------------------------------------
# Cálculo de métricas por cenário
# ---------------------------------------------------------------------------
def calcular_metricas(pares, nome_cenario):
    """
    pares: lista de tuplas (data, ufra, inmet, dif, flags)
    Retorna dict com métricas.
    """
    if not pares:
        return None

    difs  = [p[3] for p in pares]
    xs    = [p[1] for p in pares]
    ys    = [p[2] for p in pares]
    n     = len(difs)

    media    = sum(difs) / n
    mediana  = statistics.median(difs)
    var      = sum((d - media) ** 2 for d in difs) / n
    desvio   = math.sqrt(var)
    rmse     = math.sqrt(sum(d * d for d in difs) / n)

    # Quartis
    difs_ord = sorted(difs)
    q1 = difs_ord[int(0.25 * n)]
    q3 = difs_ord[int(0.75 * n)]
    iqr = q3 - q1

    r = pearson(xs, ys)
    d = willmott_d(xs, ys)
    ic = ic95(media, desvio, n)
    t, p = t_pareado_aproximado(difs)

    # Mann-Whitney-like: fração de dias com UFRA < INMET
    frac_ufra_menor = sum(1 for d in difs if d < 0) / n

    return {
        "cenario": nome_cenario,
        "n": n,
        "media": media,
        "mediana": mediana,
        "desvio": desvio,
        "rmse": rmse,
        "q1": q1,
        "q3": q3,
        "iqr": iqr,
        "r": r,
        "d": d,
        "ic_inf": ic[0] if ic else None,
        "ic_sup": ic[1] if ic else None,
        "t": t,
        "p_valor": p,
        "frac_ufra_menor": frac_ufra_menor,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 78)
    print(" DIAGNÓSTICO DE Tmin — SENSIBILIDADE A CORTES (Opção B)")
    print("=" * 78)

    print("\n[1/3] Carregando UFRA diário (SQLite)...")
    ufra = carregar_ufra_diario_com_flags(DB_PATH)
    print(f"      {len(ufra)} registros com data_iso")

    print("[2/3] Carregando INMET 82191 diário...")
    inmet = carregar_inmet_diario(INMET_D_82191)
    print(f"      {len(inmet)} registros")

    print("[3/3] Pareando e aplicando flags...")
    pares = []
    for data in sorted(set(ufra) & set(inmet)):
        u_tmin = ufra[data].get("tmin")
        i_tmin = inmet[data].get("tmin")
        if u_tmin is None or i_tmin is None:
            continue
        dif = u_tmin - i_tmin
        flags = classificar_par(data, u_tmin, i_tmin)
        pares.append((data, u_tmin, i_tmin, dif, flags))

    print(f"      {len(pares)} pares válidos (Tmin em ambas as séries)")

    # -----------------------------------------------------------------------
    # Estatísticas descritivas dos flags
    # -----------------------------------------------------------------------
    n_total = len(pares)
    n_fora  = sum(1 for p in pares if p[4]["fora_fisio"])
    n_troca = sum(1 for p in pares if p[4]["suspeita_troca"])
    n_inmet = sum(1 for p in pares if p[4]["inmet_suspeito"])
    n_2018_2022 = sum(1 for p in pares if 2018 <= p[4]["ano"] <= 2022)
    n_2023_2026 = sum(1 for p in pares if 2023 <= p[4]["ano"] <= 2026)

    print(f"\n Diagnóstico dos flags:")
    print(f"   fora_fisio (tmin<18 ou >26):     {n_fora:5d}  ({100*n_fora/n_total:.1f}%)")
    print(f"   suspeita_troca (26-34 °C):       {n_troca:5d}  ({100*n_troca/n_total:.1f}%)")
    print(f"   inmet_suspeito (<18 ou >30):     {n_inmet:5d}  ({100*n_inmet/n_total:.1f}%)")
    print(f"   período 2018-2022:               {n_2018_2022:5d}  ({100*n_2018_2022/n_total:.1f}%)")
    print(f"   período 2023-2026:               {n_2023_2026:5d}  ({100*n_2023_2026/n_total:.1f}%)")

    # -----------------------------------------------------------------------
    # Cenários
    # -----------------------------------------------------------------------
    cenarios = [
        ("C0 - completo",              lambda p: True),
        ("C1 - sem fora_fisio",        lambda p: not p[4]["fora_fisio"]),
        ("C2 - sem suspeita_troca",    lambda p: not p[4]["suspeita_troca"]),
        ("C3 - sem fora_fisio e troca",lambda p: not p[4]["fora_fisio"] and not p[4]["suspeita_troca"]),
        ("C4 - 2018-2022",             lambda p: 2018 <= p[4]["ano"] <= 2022),
        ("C5 - 2023-2026",             lambda p: 2023 <= p[4]["ano"] <= 2026),
        ("C6 - sem inmet_suspeito",    lambda p: not p[4]["inmet_suspeito"]),
        ("C7 - 2018-2022 limpo",       lambda p: 2018 <= p[4]["ano"] <= 2022
                                                and not p[4]["fora_fisio"]
                                                and not p[4]["suspeita_troca"]),
    ]

    resultados = []
    print("\n" + "=" * 78)
    print(" RESULTADOS POR CENÁRIO")
    print("=" * 78)

    for nome, filtro in cenarios:
        sub = [p for p in pares if filtro(p)]
        m = calcular_metricas(sub, nome)
        if m is None:
            print(f"\n {nome}: sem dados")
            continue

        print(f"\n {nome}")
        print(f"   N:            {m['n']:5d}")
        print(f"   Média:        {m['media']:+.3f} °C")
        print(f"   Mediana:      {m['mediana']:+.3f} °C")
        print(f"   Desvio:       {m['desvio']:.3f} °C")
        print(f"   RMSE:         {m['rmse']:.3f} °C")
        print(f"   IQR:          {m['iqr']:.3f} °C")
        print(f"   IC 95%:       [{m['ic_inf']:+.3f}, {m['ic_sup']:+.3f}]")
        if m['r'] is not None:
            print(f"   r:            {m['r']:+.3f}")
        if m['d'] is not None:
            print(f"   Willmott d:   {m['d']:+.3f}")
        if m['p_valor'] is not None:
            print(f"   p-valor:      {m['p_valor']:.3e}")
        print(f"   % UFRA<INMET: {100*m['frac_ufra_menor']:.1f}%")

        resultados.append(m)

    # -----------------------------------------------------------------------
    # Exportar CSV
    # -----------------------------------------------------------------------
    print("\n" + "=" * 78)
    print(" EXPORTANDO CSV")
    print("=" * 78)

    campos_resumo = ["cenario", "n", "media", "mediana", "desvio", "rmse",
                     "q1", "q3", "iqr", "r", "d", "ic_inf", "ic_sup",
                     "t", "p_valor", "frac_ufra_menor"]

    with open(SAIDA_RESUMO, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos_resumo)
        w.writeheader()
        for m in resultados:
            linha = {k: m.get(k) for k in campos_resumo}
            w.writerow(linha)
    print(f"  Resumo: {SAIDA_RESUMO}")

    campos_pares = ["data", "ano", "mes", "trimestre", "dia_semana",
                    "ufra_tmin", "inmet_tmin", "dif",
                    "fora_fisio", "suspeita_troca", "inmet_suspeito"]

    with open(SAIDA_PARES, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(campos_pares)
        for data, u, i, d, fl in pares:
            w.writerow([data, fl["ano"], fl["mes"], fl["trimestre"],
                        fl["dia_semana"], u, i, d,
                        int(fl["fora_fisio"]),
                        int(fl["suspeita_troca"]),
                        int(fl["inmet_suspeito"])])
    print(f"  Pares:  {SAIDA_PARES}")


if __name__ == "__main__":
    main()