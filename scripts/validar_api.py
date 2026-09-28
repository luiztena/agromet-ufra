"""
scripts/validar_api.py
----------------------
Valida se a API Flask está devolvendo os mesmos dados que estão no SQLite.
Compara campo a campo, com tolerância de arredondamento.

Uso (com o Flask rodando em outro terminal):
    python scripts/validar_api.py
"""

import json
import sqlite3
import sys
import urllib.request
from pathlib import Path


BASE_URL = "http://localhost:5000"
CAMINHO_BANCO = Path(__file__).resolve().parent.parent / "banco" / "ispaam.db"
TOLERANCIA = 0.011  # a API arredonda pra 2 casas


def api_get(caminho):
    """GET na API. Retorna dict ou None em caso de erro."""
    try:
        with urllib.request.urlopen(BASE_URL + caminho, timeout=10) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"  [ERRO] GET {caminho}: {e}")
        return None


def consultar(sql, params=()):
    con = sqlite3.connect(CAMINHO_BANCO)
    con.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in con.execute(sql, params).fetchall()]
    finally:
        con.close()


def comparar(rotulo, valor_db, valor_api):
    """Compara dois numeros com tolerancia. Retorna True se OK."""
    if valor_db is None and valor_api is None:
        return True
    if valor_db is None or valor_api is None:
        print(f"  [DIVERG] {rotulo}: banco={valor_db} | api={valor_api}")
        return False
    try:
        if abs(float(valor_db) - float(valor_api)) > TOLERANCIA:
            print(f"  [DIVERG] {rotulo}: banco={valor_db} | api={valor_api}")
            return False
        return True
    except (TypeError, ValueError):
        print(f"  [DIVERG] {rotulo}: banco={valor_db} | api={valor_api}")
        return False


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------
def teste_ultima():
    print("\n[1/4] Validando /api/ultima ...")
    resp = api_get("/api/ultima")
    if not resp:
        return False

    data_iso = resp.get("data_iso")
    linhas = consultar("""
        SELECT hora_local, tar, ur, tmin, tmax, prp, ev_mm_dia
        FROM observacoes WHERE data_iso = ?
    """, (data_iso,))

    if not linhas:
        print(f"  [ERRO] Data {data_iso} nao existe no banco")
        return False

    por_hora = {l["hora_local"]: l for l in linhas}
    l09 = por_hora.get("09:00", {})
    l15 = por_hora.get("15:00", {})

    ok = True
    ok &= comparar("tar 09h", l09.get("tar"), resp.get("temperatura_09h"))
    ok &= comparar("ur 09h",  l09.get("ur"),  resp.get("umidade_09h"))
    ok &= comparar("tmin",    l09.get("tmin"), resp.get("temp_min"))
    ok &= comparar("tmax",    l09.get("tmax"), resp.get("temp_max"))
    ok &= comparar("prp",     l09.get("prp"),  resp.get("precipitacao"))
    ok &= comparar("evap",    l09.get("ev_mm_dia"), resp.get("evaporacao"))
    ok &= comparar("tar 15h", l15.get("tar"), resp.get("temp_15h"))
    ok &= comparar("ur 15h",  l15.get("ur"),  resp.get("umidade_15h"))

    if ok:
        print(f"  [OK] /api/ultima consistente com o banco ({data_iso})")
    return ok


def teste_amostra_datas(n=20):
    print(f"\n[2/4] Validando /api/data/<data> em {n} datas aleatorias ...")
    datas = consultar("""
        SELECT data_iso FROM observacoes
        GROUP BY data_iso ORDER BY RANDOM() LIMIT ?
    """, (n,))

    total_ok = 0
    for d in datas:
        data_iso = d["data_iso"]
        dd, mm, aaaa = data_iso.split("-")[2], data_iso.split("-")[1], data_iso.split("-")[0]
        resp = api_get(f"/api/data/{dd}/{mm}/{aaaa}")
        if not resp:
            continue

        linhas = consultar("""
            SELECT hora_local, tar, ur, tmin, tmax, prp FROM observacoes WHERE data_iso = ?
        """, (data_iso,))
        por_hora = {l["hora_local"]: l for l in linhas}
        l09 = por_hora.get("09:00", {})

        ok = True
        ok &= comparar(f"{data_iso} tar",  l09.get("tar"),  resp.get("temperatura_09h"))
        ok &= comparar(f"{data_iso} ur",   l09.get("ur"),   resp.get("umidade_09h"))
        ok &= comparar(f"{data_iso} tmin", l09.get("tmin"), resp.get("temp_min"))
        ok &= comparar(f"{data_iso} tmax", l09.get("tmax"), resp.get("temp_max"))

        if ok:
            total_ok += 1

    print(f"  [OK] {total_ok}/{n} datas consistentes")
    return total_ok == n


def teste_balanco(n=10):
    print(f"\n[3/4] Validando /api/balanco/<data> em {n} datas ...")
    datas = consultar("""
        SELECT data_iso FROM observacoes
        WHERE tar IS NOT NULL AND tmin IS NOT NULL AND tmax IS NOT NULL
        GROUP BY data_iso ORDER BY RANDOM() LIMIT ?
    """, (n,))

    campos = ["Ra_Q0", "Rs", "Rso", "Kt", "PAR", "Rns", "Rnl", "Rn", "ETo"]
    total_ok = 0

    for d in datas:
        data_iso = d["data_iso"]
        dd, mm, aaaa = data_iso.split("-")[2], data_iso.split("-")[1], data_iso.split("-")[0]
        resp = api_get(f"/api/balanco/{dd}/{mm}/{aaaa}")
        if not resp or "erro" in resp:
            print(f"  [FALHA] {data_iso}: {resp}")
            continue

        faltando = [c for c in campos if c not in resp]
        if faltando:
            print(f"  [FALHA] {data_iso}: faltam campos {faltando}")
            continue
        total_ok += 1

    print(f"  [OK] {total_ok}/{n} balancos com todos os campos")
    return total_ok == n


def teste_paginacao():
    print(f"\n[4/4] Validando paginacao de /api/todas ...")
    total_db = consultar("SELECT COUNT(DISTINCT data_iso) AS n FROM observacoes")[0]["n"]

    resp = api_get("/api/todas?limite=5")
    if not resp:
        return False

    total_api = resp.get("total", 0)
    if total_db != total_api:
        print(f"  [DIVERG] total: banco={total_db} | api={total_api}")
        return False

    print(f"  [OK] total consistente ({total_db} dias)")

    # Testa o com_dados
    resp_cd = api_get("/api/todas?limite=1&com_dados=true&ano=2026")
    if resp_cd:
        total_cd = resp_cd.get("total", 0)
        print(f"  [OK] com_dados=true para 2026: {total_cd} dias com temperatura")
    return True


def main():
    if not CAMINHO_BANCO.exists():
        print(f"Banco nao encontrado: {CAMINHO_BANCO}")
        sys.exit(1)

    print("=" * 60)
    print(" VALIDACAO API x BANCO")
    print("=" * 60)

    resultados = [
        teste_ultima(),
        teste_amostra_datas(20),
        teste_balanco(10),
        teste_paginacao(),
    ]

    print("\n" + "=" * 60)
    if all(resultados):
        print(" OK - API e banco estao consistentes")
        sys.exit(0)
    else:
        print(" DIVERGENCIAS ENCONTRADAS - ver acima")
        sys.exit(1)


if __name__ == "__main__":
    main()