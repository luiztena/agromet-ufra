"""
comparar_ufra_inmet82191_A201.py
--------------------------------
Comparação TRIPLA: UFRA-BEL vs INMET 82191 (convencional) vs INMET A201 (automática).

Blocos:
  A) Horário  - Tar, UR              (UFRA x 82191 x A201)
  B) Horário  - Th2o                 (UFRA x 82191 apenas; A201 não reporta)
  C) Diário   - Tmin/Tmax            (UFRA x 82191 x A201)
  D) Diário   - Tmin "janela UFRA"   (UFRA x A201 apenas, 03-12 UTC)
  E) Diário   - Precipitação         (UFRA x 82191 x A201)
  F) Diário   - Evaporação (Piche)   (UFRA x 82191 apenas)

Saídas:
  - comparacao_tripla_completo.csv  (todos os pares)
  - comparacao_tripla_resumo.csv    (métricas por variável x par de estações)

Uso:
    python scripts/_debug/comparar_ufra_inmet82191_A201.py
"""

import csv
import math
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
BASE = Path(__file__).resolve().parent.parent.parent
DB_PATH        = BASE / "banco" / "ispaam.db"
INMET_H_82191  = BASE / "dados_82191_H_2018-01-01_2025-12-31.csv"
INMET_D_82191  = BASE / "dados_82191_D_2018-01-01_2025-12-31.csv"
INMET_H_A201   = BASE / "dados_A201_H_2018-01-01_2025-12-31.csv"

SAIDA_COMPLETO = BASE / "comparacao_tripla_completo.csv"
SAIDA_RESUMO   = BASE / "comparacao_tripla_resumo.csv"

# Pareamento horário UFRA -> UTC
PARES_HORA = [("09:00", "1200"), ("15:00", "1800")]

# Janela da UFRA (para Tmin/Tmax "recalculada" da A201)
JANELA_UFRA_INICIO_UTC = "0300"   # 00:00 local
JANELA_UFRA_FIM_UTC    = "1200"   # 09:00 local

# Critérios por variável
CRITERIOS = {
    "temperatura": {"rmse_max": 1.6, "vies_max": 1.0, "r_min": 0.8, "d_min": 0.8, "unidade": "°C"},
    "ur":          {"rmse_max": 10.0, "vies_max": 5.0, "r_min": 0.7, "d_min": 0.8, "unidade": "%"},
    "precipitacao":{"rmse_max": None, "vies_max": None, "r_min": 0.6, "d_min": 0.7, "unidade": "mm"},
    "evaporacao":  {"rmse_max": None, "vies_max": None, "r_min": None, "d_min": None, "unidade": "mm"},
}

SIGMA = 3.0


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


def estatisticas(difs):
    n = len(difs)
    if n == 0:
        return None
    vies = sum(difs) / n
    var = sum((d - vies) ** 2 for d in difs) / n
    desvio = math.sqrt(var)
    rmse = math.sqrt(sum(d * d for d in difs) / n)
    return {"n": n, "vies": vies, "desvio": desvio, "rmse": rmse}


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


def ic95(vies, desvio, n):
    if n < 2:
        return None
    se = desvio / math.sqrt(n)
    return (vies - 1.96 * se, vies + 1.96 * se)


def contar_outliers(difs, vies, desvio, sigma=SIGMA):
    if desvio == 0:
        return 0
    return sum(1 for d in difs if abs(d - vies) > sigma * desvio)


def normalizar_data(s):
    s = str(s).strip()
    if not s:
        return None
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        try:
            return datetime.strptime(s[:10], "%d/%m/%Y").strftime("%Y-%m-%d")
        except ValueError:
            return None


def soma_utc(hhmm, horas):
    """Soma horas a um HHMM UTC (string). Retorna HHMM."""
    h = int(hhmm[:2])
    m = int(hhmm[2:])
    total = (h * 60 + m + horas * 60) % (24 * 60)
    return f"{total // 60:02d}{total % 60:02d}"


# ---------------------------------------------------------------------------
# 1. INMET 82191 horário (convencional)
# ---------------------------------------------------------------------------
def carregar_inmet_horario(caminho):
    with open(caminho, encoding="utf-8") as f:
        linhas = f.readlines()

    idx_cab = next((i for i, l in enumerate(linhas) if l.startswith("Data Medicao")), None)
    if idx_cab is None:
        raise RuntimeError(f"Cabeçalho horário não encontrado em {caminho}")

    cabecalho = [c.strip() for c in linhas[idx_cab].strip().split(";")]
    idx = {nome: j for j, nome in enumerate(cabecalho)}

    col_data = idx["Data Medicao"]
    col_hora = idx["Hora Medicao"]
    col_tar  = idx["TEMPERATURA DO AR - BULBO SECO, HORARIA(°C)"]
    col_th2o = idx["TEMPERATURA DO AR - BULBO UMIDO, HORARIA(°C)"]
    col_ur   = idx["UMIDADE RELATIVA DO AR, HORARIA(%)"]

    inmet = {}
    for linha in linhas[idx_cab + 1:]:
        partes = [p.strip() for p in linha.strip().split(";")]
        if len(partes) <= max(col_data, col_hora, col_tar, col_th2o, col_ur):
            continue
        data = normalizar_data(partes[col_data])
        hora = partes[col_hora].zfill(4)
        if not data or not hora:
            continue
        inmet[(data, hora)] = {
            "tar":     para_float(partes[col_tar]),
            "th2o_ev": para_float(partes[col_th2o]),
            "ur":      para_float(partes[col_ur]),
        }
    return inmet


# ---------------------------------------------------------------------------
# 2. INMET 82191 diário
# ---------------------------------------------------------------------------
def carregar_inmet_diario(caminho):
    with open(caminho, encoding="utf-8") as f:
        linhas = f.readlines()

    idx_cab = next((i for i, l in enumerate(linhas) if l.startswith("Data Medicao")), None)
    if idx_cab is None:
        raise RuntimeError(f"Cabeçalho diário não encontrado em {caminho}")

    cabecalho = [c.strip() for c in linhas[idx_cab].strip().split(";")]
    idx = {nome: j for j, nome in enumerate(cabecalho)}

    col_data  = idx["Data Medicao"]
    col_tmax  = idx["TEMPERATURA MAXIMA, DIARIA(°C)"]
    col_tmin  = idx["TEMPERATURA MINIMA, DIARIA(°C)"]
    col_prp   = idx["PRECIPITACAO TOTAL, DIARIO(mm)"]
    col_evp   = idx["EVAPORACAO DO PICHE, DIARIA(mm)"]

    inmet_d = {}
    for linha in linhas[idx_cab + 1:]:
        partes = [p.strip() for p in linha.strip().split(";")]
        if len(partes) <= max(col_data, col_tmax, col_tmin, col_prp, col_evp):
            continue
        data = normalizar_data(partes[col_data])
        if not data:
            continue
        inmet_d[data] = {
            "tmax":     para_float(partes[col_tmax]),
            "tmin":     para_float(partes[col_tmin]),
            "prp_dia":  para_float(partes[col_prp]),
            "ev_piche": para_float(partes[col_evp]),
        }
    return inmet_d


# ---------------------------------------------------------------------------
# 3. INMET A201 horário (automática)
# ---------------------------------------------------------------------------
def carregar_a201_horario(caminho):
    """
    Retorna dict:
        a201[(data, HHMM)] = {
            'tar': ..., 'ur': ..., 'prp': ...,
            'tmax_hora_ant': ..., 'tmin_hora_ant': ...,
            'ur_max_hora_ant': ..., 'ur_min_hora_ant': ...
        }
    """
    with open(caminho, encoding="utf-8") as f:
        linhas = f.readlines()

    idx_cab = next((i for i, l in enumerate(linhas) if l.startswith("Data Medicao")), None)
    if idx_cab is None:
        raise RuntimeError(f"Cabeçalho A201 não encontrado em {caminho}")

    cabecalho = [c.strip() for c in linhas[idx_cab].strip().split(";")]
    idx = {nome: j for j, nome in enumerate(cabecalho)}

    col_data     = idx["Data Medicao"]
    col_hora     = idx["Hora Medicao"]
    col_prp      = idx["PRECIPITACAO TOTAL, HORARIO(mm)"]
    col_tar      = idx["TEMPERATURA DO AR - BULBO SECO, HORARIA(°C)"]
    col_tmax_ant = idx["TEMPERATURA MAXIMA NA HORA ANT. (AUT)(°C)"]
    col_tmin_ant = idx["TEMPERATURA MINIMA NA HORA ANT. (AUT)(°C)"]
    col_urmax_ant= idx["UMIDADE REL. MAX. NA HORA ANT. (AUT)(%)"]
    col_urmin_ant= idx["UMIDADE REL. MIN. NA HORA ANT. (AUT)(%)"]
    col_ur       = idx["UMIDADE RELATIVA DO AR, HORARIA(%)"]

    a201 = {}
    for linha in linhas[idx_cab + 1:]:
        partes = [p.strip() for p in linha.strip().split(";")]
        if len(partes) <= max(col_data, col_hora, col_prp, col_tar, col_tmax_ant,
                              col_tmin_ant, col_urmax_ant, col_urmin_ant, col_ur):
            continue
        data = normalizar_data(partes[col_data])
        hora = partes[col_hora].zfill(4)
        if not data or not hora:
            continue
        a201[(data, hora)] = {
            "tar":            para_float(partes[col_tar]),
            "ur":             para_float(partes[col_ur]),
            "prp":            para_float(partes[col_prp]),
            "tmax_hora_ant":  para_float(partes[col_tmax_ant]),
            "tmin_hora_ant":  para_float(partes[col_tmin_ant]),
            "ur_max_hora_ant":para_float(partes[col_urmax_ant]),
            "ur_min_hora_ant":para_float(partes[col_urmin_ant]),
        }
    return a201


# ---------------------------------------------------------------------------
# 4. UFRA horário / diário (do SQLite)
# ---------------------------------------------------------------------------
def carregar_ufra_horario(caminho_db, estacao_id=None):
    con = sqlite3.connect(caminho_db)
    cur = con.cursor()
    sql = """
        SELECT data_iso, hora_local, tar, th2o_ev, ur, prp
        FROM observacoes
        WHERE hora_local IN ('09:00', '15:00')
    """
    params = []
    if estacao_id is not None:
        sql += " AND estacao_id = ?"
        params.append(estacao_id)

    ufra = {}
    for row in cur.execute(sql, params):
        data_iso, hora_local, tar, th2o, ur, prp = row
        if data_iso is None or hora_local is None:
            continue
        h = str(hora_local).strip()
        if len(h) == 4 and h.isdigit():
            h = f"{h[:2]}:{h[2:]}"
        ufra[(data_iso, h)] = {"tar": tar, "th2o_ev": th2o, "ur": ur, "prp": prp}
    con.close()
    return ufra


def carregar_ufra_diario(caminho_db, estacao_id=None):
    con = sqlite3.connect(caminho_db)
    cur = con.cursor()

    cur.execute("PRAGMA table_info(observacoes)")
    cols = {r[1] for r in cur.fetchall()}

    def pick(*nomes):
        for n in nomes:
            if n in cols:
                return n
        return None

    c_tmax = pick("tmax_real", "tmax")
    c_tmin = pick("tmin_real", "tmin")
    c_prp  = pick("prp_dia", "prp")
    c_ev   = pick("ev_mm_dia", "ev_dia", "ev_mm")

    if not (c_tmax and c_tmin):
        con.close()
        return None

    sql = f"""
        SELECT data_iso, {c_tmax}, {c_tmin}
        {", " + c_prp if c_prp else ""}
        {", " + c_ev if c_ev else ""}
        FROM observacoes
        WHERE hora_local = '09:00'
    """
    params = []
    if estacao_id is not None:
        sql += " AND estacao_id = ?"
        params.append(estacao_id)

    ufra_d = {}
    for row in cur.execute(sql, params):
        data_iso = row[0]
        if data_iso is None:
            continue
        ufra_d[data_iso] = {
            "tmax": row[1],
            "tmin": row[2],
            "prp":  row[3] if c_prp else None,
            "ev":   row[4] if c_ev else None,
        }
    con.close()
    return ufra_d


# ---------------------------------------------------------------------------
# 5. Deriva Tmin/Tmax diárias da A201
# ---------------------------------------------------------------------------
def derivar_diario_a201(a201, janela=None):
    """
    Retorna dict:
        a201_d[data] = {'tmax': ..., 'tmin': ..., 'prp_dia': ...}

    Se janela = (HHMM_ini, HHMM_fim) em UTC, restringe a Tmin/Tmax a essa janela.
    Caso contrário, usa o dia inteiro (00-23 UTC).

    Usa tmax_hora_ant / tmin_hora_ant (valores da hora anterior) para capturar
    extremos que ocorreram em qualquer momento dentro da janela.
    """
    a201_d = {}
    for (data, hora), v in a201.items():
        if janela is not None:
            if not (janela[0] <= hora <= janela[1]):
                continue

        d = a201_d.setdefault(data, {
            "tmax": None, "tmin": None, "prp_dia": 0.0,
            "n_tmax": 0, "n_tmin": 0
        })

        # Tmax: usa o máximo de tmax_hora_ant (que já é o máximo da hora anterior)
        if v["tmax_hora_ant"] is not None:
            if d["tmax"] is None or v["tmax_hora_ant"] > d["tmax"]:
                d["tmax"] = v["tmax_hora_ant"]
            d["n_tmax"] += 1

        # Tmin: usa o mínimo de tmin_hora_ant
        if v["tmin_hora_ant"] is not None:
            if d["tmin"] is None or v["tmin_hora_ant"] < d["tmin"]:
                d["tmin"] = v["tmin_hora_ant"]
            d["n_tmin"] += 1

        # Precipitação: soma
        if v["prp"] is not None:
            d["prp_dia"] += v["prp"]

    # Remove dias sem nenhum extremo
    return {k: v for k, v in a201_d.items() if v["tmax"] is not None or v["tmin"] is not None}


# ---------------------------------------------------------------------------
# 6. Comparação genérica (dois dicts)
# ---------------------------------------------------------------------------
def comparar_dicts(ufra_dict, inmet_dict, chave_ufra, chave_inmet, rotulo, tipo_criterio):
    pares = []
    for chave, v_ufra_dict in ufra_dict.items():
        v_ufra = v_ufra_dict.get(chave_ufra) if isinstance(v_ufra_dict, dict) else None
        v_inmet = inmet_dict.get(chave, {}).get(chave_inmet)
        if v_ufra is None or v_inmet is None:
            continue
        pares.append((chave, v_ufra, v_inmet, v_ufra - v_inmet))

    if not pares:
        return None
    return _resumo(pares, rotulo, tipo_criterio)


def comparar_horario(ufra, inmet, nome_ufra, nome_inmet, rotulo, tipo_criterio):
    pares = []
    for hora_ufra, hora_utc in PARES_HORA:
        for (data, hora), v_ufra_dict in ufra.items():
            if hora != hora_ufra:
                continue
            v_ufra = v_ufra_dict.get(nome_ufra)
            v_inmet = inmet.get((data, hora_utc), {}).get(nome_inmet)
            if v_ufra is None or v_inmet is None:
                continue
            pares.append(((data, hora_ufra), v_ufra, v_inmet, v_ufra - v_inmet))

    if not pares:
        return None
    return _resumo(pares, rotulo, tipo_criterio)


def _resumo(pares, rotulo, tipo_criterio):
    difs = [p[3] for p in pares]
    xs = [p[1] for p in pares]
    ys = [p[2] for p in pares]
    est = estatisticas(difs)
    r = pearson(xs, ys)
    d = willmott_d(xs, ys)
    n_out = contar_outliers(difs, est["vies"], est["desvio"])
    return {
        "rotulo": rotulo,
        "tipo": tipo_criterio,
        "n": est["n"],
        "vies": est["vies"],
        "desvio": est["desvio"],
        "rmse": est["rmse"],
        "r": r, "d": d,
        "ic": ic95(est["vies"], est["desvio"], est["n"]),
        "n_outliers": n_out,
        "pct_outliers": 100.0 * n_out / est["n"] if est["n"] else 0.0,
        "pares": pares,
    }


# ---------------------------------------------------------------------------
# 7. Relatório
# ---------------------------------------------------------------------------
def imprimir_resultado(res, titulo_extra=None):
    if res is None:
        print("  (sem dados em comum)\n")
        return
    crit = CRITERIOS[res["tipo"]]
    u = crit["unidade"]
    if titulo_extra:
        print(f"  >> {titulo_extra}")
    print(f"  N pareado:    {res['n']}")
    print(f"  Viés:         {res['vies']:+.2f} {u}")
    print(f"  Desvio:       {res['desvio']:.2f} {u}")
    print(f"  RMSE:         {res['rmse']:.2f} {u}")
    if res["r"] is not None:
        print(f"  Correlação:   {res['r']:+.3f}")
    if res["d"] is not None:
        print(f"  Willmott d:   {res['d']:+.3f}")
    if res["ic"] is not None:
        print(f"  IC 95%:       [{res['ic'][0]:+.2f}, {res['ic'][1]:+.2f}]")
    print(f"  Outliers 3σ:  {res['n_outliers']} ({res['pct_outliers']:.1f}%)")

    checks = []
    if crit["rmse_max"] is not None:
        checks.append((f"RMSE < {crit['rmse_max']} {u}", res["rmse"] < crit["rmse_max"]))
    if crit["vies_max"] is not None:
        checks.append((f"|Viés| < {crit['vies_max']} {u}", abs(res["vies"]) < crit["vies_max"]))
    if crit["r_min"] is not None:
        checks.append((f"r > {crit['r_min']}", res["r"] is not None and res["r"] > crit["r_min"]))
    if crit["d_min"] is not None:
        checks.append((f"Willmott d > {crit['d_min']}", res["d"] is not None and res["d"] > crit["d_min"]))
    if checks:
        print("  Critérios:")
        for nome, ok in checks:
            print(f"    {'OK   ' if ok else 'FALHA'} {nome}")
    print()


def imprimir_trio(res_a, res_b, titulo_a, titulo_b, titulo_var):
    """Imprime dois resultados lado a lado (ex: UFRA x 82191 e UFRA x A201)."""
    print("-" * 70)
    print(f" {titulo_var}")
    print("-" * 70)
    imprimir_resultado(res_a, titulo_extra=titulo_a)
    imprimir_resultado(res_b, titulo_extra=titulo_b)


# ---------------------------------------------------------------------------
# 8. main
# ---------------------------------------------------------------------------
def main():
    print("=" * 74)
    print(" COMPARAÇÃO TRIPLA: UFRA-BEL vs INMET 82191 vs INMET A201")
    print("=" * 74)

    # --- Carrega tudo ---
    print("\n[1/6] INMET 82191 horário...")
    inmet_h = carregar_inmet_horario(INMET_H_82191)
    print(f"      {len(inmet_h)} registros")

    print("[2/6] INMET 82191 diário...")
    inmet_d = carregar_inmet_diario(INMET_D_82191)
    print(f"      {len(inmet_d)} registros")

    print("[3/6] INMET A201 horário...")
    a201 = carregar_a201_horario(INMET_H_A201)
    print(f"      {len(a201)} registros")

    print("[4/6] UFRA horário (SQLite)...")
    ufra_h = carregar_ufra_horario(DB_PATH)
    print(f"      {len(ufra_h)} registros")

    print("[5/6] UFRA diário (SQLite)...")
    ufra_d = carregar_ufra_diario(DB_PATH)
    if ufra_d is None:
        print("      [AVISO] Sem colunas tmax/tmin no SQLite. Bloco diário será pulado.")
    else:
        print(f"      {len(ufra_d)} registros")

    print("[6/6] Derivando Tmin/Tmax diárias da A201...")
    a201_dia_completo = derivar_diario_a201(a201, janela=None)
    a201_dia_janela   = derivar_diario_a201(
        a201, janela=(JANELA_UFRA_INICIO_UTC, JANELA_UFRA_FIM_UTC)
    )
    print(f"      Dia completo: {len(a201_dia_completo)} dias")
    print(f"      Janela UFRA ({JANELA_UFRA_INICIO_UTC}-{JANELA_UFRA_FIM_UTC} UTC): "
          f"{len(a201_dia_janela)} dias")

    resultados = []

    # -----------------------------------------------------------------------
    # BLOCO A: variáveis horárias
    # -----------------------------------------------------------------------
    print("\n" + "=" * 74)
    print(" BLOCO A — VARIÁVEIS HORÁRIAS")
    print("=" * 74)

    for nome_u, nome_i, nome_a, rotulo, tipo in [
        ("tar", "tar", "tar", "Tar instantânea (09h/15h)", "temperatura"),
        ("ur",  "ur",  "ur",  "UR (09h/15h)",               "ur"),
    ]:
        res_82191 = comparar_horario(ufra_h, inmet_h, nome_u, nome_i,
                                     rotulo, tipo)
        res_a201  = comparar_horario(ufra_h, a201,    nome_u, nome_a,
                                     rotulo, tipo)
        imprimir_trio(
            res_82191, res_a201,
            "UFRA x 82191 (convencional)",
            "UFRA x A201 (automática)",
            rotulo,
        )
        if res_82191: resultados.append(res_82191)
        if res_a201:  resultados.append(res_a201)

    # Th2o só contra 82191 (A201 não reporta bulbo úmido)
    print("-" * 70)
    print(" Th2o (bulbo úmido) — apenas UFRA x 82191")
    print(" (A201 não reporta bulbo úmido; apenas UR)")
    print("-" * 70)
    res_th2o = comparar_horario(ufra_h, inmet_h, "th2o_ev", "th2o_ev",
                                "Th2o (09h/15h)", "temperatura")
    imprimir_resultado(res_th2o)
    if res_th2o: resultados.append(res_th2o)

    # -----------------------------------------------------------------------
    # BLOCO B: diário Tmin/Tmax
    # -----------------------------------------------------------------------
    if ufra_d is not None:
        print("\n" + "=" * 74)
        print(" BLOCO B — Tmin/Tmax DIÁRIAS")
        print("=" * 74)

        # Tmax
        res_tmax_82191 = comparar_dicts(ufra_d, inmet_d, "tmax", "tmax",
                                        "Tmax diária", "temperatura")
        res_tmax_a201  = comparar_dicts(ufra_d, a201_dia_completo, "tmax", "tmax",
                                        "Tmax diária (A201 dia completo)", "temperatura")
        imprimir_trio(
            res_tmax_82191, res_tmax_a201,
            "UFRA x 82191 (convencional)",
            "UFRA x A201 (dia completo)",
            "Tmax diária",
        )
        if res_tmax_82191: resultados.append(res_tmax_82191)
        if res_tmax_a201:  resultados.append(res_tmax_a201)

        # Tmin
        res_tmin_82191 = comparar_dicts(ufra_d, inmet_d, "tmin", "tmin",
                                        "Tmin diária", "temperatura")
        res_tmin_a201  = comparar_dicts(ufra_d, a201_dia_completo, "tmin", "tmin",
                                        "Tmin diária (A201 dia completo)", "temperatura")
        imprimir_trio(
            res_tmin_82191, res_tmin_a201,
            "UFRA x 82191 (convencional)",
            "UFRA x A201 (dia completo)",
            "Tmin diária",
        )
        if res_tmin_82191: resultados.append(res_tmin_82191)
        if res_tmin_a201:  resultados.append(res_tmin_a201)

        # -------------------------------------------------------------------
        # BLOCO D: Tmin/Tmax recalculadas na janela UFRA (só A201)
        # -------------------------------------------------------------------
        print("\n" + "=" * 74)
        print(" BLOCO D — Tmin/Tmax NA JANELA UFRA (apenas A201)")
        print(f" Janela: {JANELA_UFRA_INICIO_UTC}-{JANELA_UFRA_FIM_UTC} UTC "
              f"(= 00h-09h local)")
        print("=" * 74)

        res_tmin_a201_jan = comparar_dicts(
            ufra_d, a201_dia_janela, "tmin", "tmin",
            "Tmin diária (A201 janela UFRA)", "temperatura"
        )
        res_tmax_a201_jan = comparar_dicts(
            ufra_d, a201_dia_janela, "tmax", "tmax",
            "Tmax diária (A201 janela UFRA)", "temperatura"
        )

        print("-" * 70)
        print(" Tmin: UFRA x A201 janela UFRA  vs  UFRA x A201 dia completo")
        print("-" * 70)
        imprimir_resultado(res_tmin_a201_jan,
                           titulo_extra="UFRA x A201 (janela 00-09h local)")
        if res_tmin_a201_jan: resultados.append(res_tmin_a201_jan)

        print("-" * 70)
        print(" Tmax: UFRA x A201 janela UFRA  vs  UFRA x A201 dia completo")
        print("-" * 70)
        imprimir_resultado(res_tmax_a201_jan,
                           titulo_extra="UFRA x A201 (janela 00-09h local)")
        if res_tmax_a201_jan: resultados.append(res_tmax_a201_jan)

        # -------------------------------------------------------------------
        # BLOCO E: precipitação
        # -------------------------------------------------------------------
        print("\n" + "=" * 74)
        print(" BLOCO E — PRECIPITAÇÃO DIÁRIA")
        print("=" * 74)

        res_prp_82191 = comparar_dicts(ufra_d, inmet_d, "prp", "prp_dia",
                                       "Precipitação diária", "precipitacao")
        res_prp_a201  = comparar_dicts(ufra_d, a201_dia_completo, "prp", "prp_dia",
                                       "Precipitação diária (A201)", "precipitacao")
        imprimir_trio(
            res_prp_82191, res_prp_a201,
            "UFRA x 82191 (convencional)",
            "UFRA x A201 (automática)",
            "Precipitação diária",
        )
        if res_prp_82191: resultados.append(res_prp_82191)
        if res_prp_a201:  resultados.append(res_prp_a201)

        # -------------------------------------------------------------------
        # BLOCO F: evaporação (só 82191 tem Piche)
        # -------------------------------------------------------------------
        print("\n" + "=" * 74)
        print(" BLOCO F — EVAPORAÇÃO (apenas UFRA x 82191)")
        print(" ATENÇÃO: Piche != Tanque Classe A. Comparação qualitativa.")
        print("=" * 74)
        res_ev = comparar_dicts(ufra_d, inmet_d, "ev", "ev_piche",
                                "Evaporação", "evaporacao")
        imprimir_resultado(res_ev)
        if res_ev: resultados.append(res_ev)

    # -----------------------------------------------------------------------
    # Exporta CSV completo
    # -----------------------------------------------------------------------
    if resultados:
        with open(SAIDA_COMPLETO, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["variavel", "par", "chave", "valor_ufra", "valor_ref", "diferenca"])
            for res in resultados:
                for p in res["pares"]:
                    w.writerow([res["rotulo"], "", p[0], p[1], p[2], p[3]])
        print(f"\nPares salvos em: {SAIDA_COMPLETO}")

        # Resumo
        with open(SAIDA_RESUMO, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["variavel", "n", "vies", "desvio", "rmse", "r", "d",
                        "ic_inf", "ic_sup", "pct_outliers"])
            for res in resultados:
                ic = res["ic"] if res["ic"] else (None, None)
                w.writerow([
                    res["rotulo"], res["n"], f"{res['vies']:.4f}",
                    f"{res['desvio']:.4f}", f"{res['rmse']:.4f}",
                    f"{res['r']:.4f}" if res["r"] is not None else "",
                    f"{res['d']:.4f}" if res["d"] is not None else "",
                    f"{ic[0]:.4f}" if ic[0] is not None else "",
                    f"{ic[1]:.4f}" if ic[1] is not None else "",
                    f"{res['pct_outliers']:.2f}",
                ])
        print(f"Resumo salvo em: {SAIDA_RESUMO}")


if __name__ == "__main__":
    main()