"""
teste_offset_dia.py
-------------------
Testa 3 pareamentos para Tmin/Tmax:
  A) UFRA linha D  <->  INMET dia D      (atual)
  B) UFRA linha D  <->  INMET dia D-1    (hipótese: offset de 1 dia)
  C) UFRA linha D  <->  INMET dia D+1    (controle)

Uso:
    python scripts/_debug/teste_offset_dia.py
"""

import math
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

BASE = Path(__file__).resolve().parent.parent.parent
DB_PATH = BASE / "banco" / "ispaam.db"
INMET_D_CSV = BASE / "dados_82191_D_2018-01-01_2025-12-31.csv"


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
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s[:10], fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def shift_data(data_iso, dias):
    d = datetime.strptime(data_iso, "%Y-%m-%d")
    return (d + timedelta(days=dias)).strftime("%Y-%m-%d")


def media(xs):
    return sum(xs) / len(xs) if xs else None


def desvio(xs):
    if len(xs) < 2:
        return None
    m = media(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def pearson(xs, ys):
    n = len(xs)
    if n < 2:
        return None
    mx, my = media(xs), media(ys)
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
    m = media(obs)
    num = sum((obs[i] - mod[i]) ** 2 for i in range(n))
    den = sum((abs(obs[i] - m) + abs(mod[i] - m)) ** 2 for i in range(n))
    if den == 0:
        return None
    return 1 - num / den


# ---------------------------------------------------------------------------
# Carregamento
# ---------------------------------------------------------------------------
def carregar_inmet_diario(caminho):
    with open(caminho, encoding="utf-8") as f:
        linhas = f.readlines()
    idx_cab = next(i for i, l in enumerate(linhas) if l.startswith("Data Medicao"))
    cabecalho = [c.strip() for c in linhas[idx_cab].strip().split(";")]
    idx = {n: j for j, n in enumerate(cabecalho)}

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


def carregar_ufra_diario(caminho_db):
    """Só a linha das 09:00 (onde Tmin/Tmax são registrados)."""
    con = sqlite3.connect(caminho_db)
    cur = con.cursor()
    sql = """
        SELECT data_iso, tmax_real, tmin_real
        FROM observacoes
        WHERE hora_local = '09:00'
    """
    ufra = {}
    for data, tmax, tmin in cur.execute(sql):
        if data is None:
            continue
        ufra[data] = {"tmax": tmax, "tmin": tmin}
    con.close()
    return ufra


# ---------------------------------------------------------------------------
# Análise
# ---------------------------------------------------------------------------
def estatisticas_pareamento(pares):
    if not pares:
        return None
    difs = [p[2] for p in pares]
    ufras = [p[0] for p in pares]
    inmes = [p[1] for p in pares]
    v = media(difs)
    s = desvio(difs)
    rmse = math.sqrt(sum(d * d for d in difs) / len(difs))
    return {
        "n": len(pares),
        "vies": v,
        "desvio": s,
        "rmse": rmse,
        "r": pearson(ufras, inmes),
        "d": willmott_d(ufras, inmes),
    }


def montar_pares(ufra, inmet, offset_dias, chave):
    """
    offset_dias: quantos dias somar à data da UFRA para parear.
      offset = 0   -> UFRA D <-> INMET D
      offset = +1  -> UFRA D <-> INMET D+1
      offset = -1  -> UFRA D <-> INMET D-1
    """
    pares = []
    for data_u, v_u in ufra.items():
        v = v_u.get(chave)
        if v is None:
            continue
        data_i = shift_data(data_u, offset_dias)
        v_i = inmet.get(data_i, {}).get(chave)
        if v_i is None:
            continue
        pares.append((v, v_i, v - v_i))
    return pares


def imprimir_teste(titulo, res):
    print(f"  {titulo}")
    if res is None:
        print("    (sem dados)\n")
        return
    print(f"    N:    {res['n']}")
    print(f"    Viés: {res['vies']:+.3f}")
    print(f"    RMSE: {res['rmse']:.3f}")
    print(f"    r:    {res['r']:+.3f}")
    print(f"    d:    {res['d']:+.3f}")
    print()


def main():
    print("Carregando dados...")
    inmet = carregar_inmet_diario(INMET_D_CSV)
    ufra = carregar_ufra_diario(DB_PATH)
    print(f"  INMET: {len(inmet)} dias")
    print(f"  UFRA:  {len(ufra)} dias\n")

    for chave, rotulo in [("tmin", "TMIN"), ("tmax", "TMAX")]:
        print("=" * 70)
        print(f" {rotulo} — TESTE DE OFFSET DE DIA")
        print("=" * 70)
        print()

        for offset, nome in [(0, "A) UFRA D <-> INMET D      (atual)"),
                             (-1, "B) UFRA D <-> INMET D-1    (hipótese: Tmin/Tmax são de D-1)"),
                             (+1, "C) UFRA D <-> INMET D+1    (controle)")]:
            pares = montar_pares(ufra, inmet, offset, chave)
            res = estatisticas_pareamento(pares)
            imprimir_teste(nome, res)

        # Veredito
        print(f"  Veredito {rotulo}:")
        print(f"    O melhor pareamento é o que tem |viés| mais próximo de 0 E r mais alto.")
        print()

    print("=" * 70)
    print(" INTERPRETAÇÃO")
    print("=" * 70)
    print("""
  Se o teste B (offset = -1) tem:
    - |viés| próximo de 0
    - r mais alto que A
  Então o pareamento correto é UFRA D <-> INMET D-1.
  Isso confirma que Tmin/Tmax da UFRA na linha das 09:00 são do dia anterior.

  Se o teste A continua sendo o melhor, o offset não é a causa.
""")


if __name__ == "__main__":
    main()