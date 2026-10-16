"""
verificar_integridade_db.py
---------------------------
Verifica a integridade do banco SQLite após as mudanças.

Checa:
  1. Arquivo existe e tem tamanho razoável
  2. PRAGMA integrity_check (verificação nativa do SQLite)
  3. Estrutura da tabela 'observacoes'
  4. Cobertura por ano (quantos registros por ano)
  5. Campos nulos por ano (tmin, tmax, tar, ur, prp)
  6. Duplicatas
  7. Valores fora de faixas plausíveis
  8. Comparação rápida com os JSONs

Saída:
  - Impressão na tela
  - relatorios/integridade_db_YYYYMMDD_HHMMSS.txt
"""

import csv
import sqlite3
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
BASE = Path(r"C:\Users\luizt\Desktop\ISPAAM API\agromet-ufra")
DB_PATH = BASE / "banco" / "ispaam.db"
DIR_JSON = BASE / "dados_brutos"
DIR_RELATORIOS = BASE / "relatorios"

DIR_RELATORIOS.mkdir(parents=True, exist_ok=True)

TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
SAIDA_TXT = DIR_RELATORIOS / f"integridade_db_{TIMESTAMP}.txt"

ANOS = list(range(2018, 2027))


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


# ---------------------------------------------------------------------------
# Coletor de saída (imprime e grava no arquivo)
# ---------------------------------------------------------------------------
class Reporter:
    def __init__(self, arquivo):
        self.linhas = []
        self.arquivo = arquivo

    def p(self, texto=""):
        print(texto)
        self.linhas.append(texto)

    def salvar(self):
        with open(self.arquivo, "w", encoding="utf-8") as f:
            f.write("\n".join(self.linhas))


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------
def teste_arquivo(r):
    r.p("=" * 74)
    r.p(" 1. ARQUIVO")
    r.p("=" * 74)

    if not DB_PATH.exists():
        r.p(f" [FALHA] Arquivo não encontrado: {DB_PATH}")
        return False

    tamanho_mb = DB_PATH.stat().st_size / (1024 * 1024)
    r.p(f" Caminho:  {DB_PATH}")
    r.p(f" Tamanho:  {tamanho_mb:.2f} MB")

    if tamanho_mb < 0.1:
        r.p(" [AVISO] Arquivo muito pequeno. Pode estar corrompido.")
        return False

    r.p(" [OK]")
    r.p()
    return True


def teste_integrity_check(r):
    r.p("=" * 74)
    r.p(" 2. PRAGMA INTEGRITY_CHECK")
    r.p("=" * 74)

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("PRAGMA integrity_check")
    resultado = cur.fetchall()
    con.close()

    if resultado == [("ok",)]:
        r.p(" [OK] SQLite reporta integridade OK.")
        r.p()
        return True
    else:
        r.p(" [FALHA] Problemas detectados:")
        for linha in resultado:
            r.p(f"   {linha}")
        r.p()
        return False


def teste_estrutura(r):
    r.p("=" * 74)
    r.p(" 3. ESTRUTURA DA TABELA")
    r.p("=" * 74)

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    # Tabelas existentes
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tabelas = [row[0] for row in cur.fetchall()]
    r.p(f" Tabelas: {tabelas}")

    if "observacoes" not in tabelas:
        r.p(" [FALHA] Tabela 'observacoes' não encontrada.")
        con.close()
        return False

    # Colunas da tabela
    cur.execute("PRAGMA table_info(observacoes)")
    colunas = cur.fetchall()
    r.p(f" Colunas em 'observacoes': {len(colunas)}")
    for c in colunas:
        cid, nome, tipo, notnull, default, pk = c
        r.p(f"   [{cid}] {nome:<30} {tipo:<12} notnull={notnull} pk={pk}")

    con.close()
    r.p(" [OK]")
    r.p()
    return True


def teste_cobertura(r):
    r.p("=" * 74)
    r.p(" 4. COBERTURA POR ANO")
    r.p("=" * 74)

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cur.execute("""
        SELECT strftime('%Y', data_iso) AS ano,
               COUNT(*) AS total
        FROM observacoes
        GROUP BY ano
        ORDER BY ano
    """)
    por_ano = {row[0]: row[1] for row in cur.fetchall()}

    r.p(f" {'Ano':<6} {'Total':>8}  {'Esperado':>10}  {'Status':>10}")
    r.p(" " + "-" * 42)

    tudo_ok = True
    for ano in ANOS:
        ano_str = str(ano)
        total = por_ano.get(ano_str, 0)
        esperado = 730  # 2 registros por dia × 365
        status = "OK" if total >= 700 else "BAIXO"
        if total < 700:
            tudo_ok = False
        r.p(f" {ano:<6} {total:>8}  {esperado:>10}  {status:>10}")

    con.close()
    r.p()
    return tudo_ok


def teste_nulos(r):
    r.p("=" * 74)
    r.p(" 5. NULOS POR CAMPO POR ANO")
    r.p("=" * 74)

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    # Descobre colunas de interesse
    cur.execute("PRAGMA table_info(observacoes)")
    cols = {row[1] for row in cur.fetchall()}

    campos = []
    for c in ["tar", "tmax_real", "tmin_real", "tmax", "tmin", "ur", "prp", "tmed"]:
        if c in cols:
            campos.append(c)

    if not campos:
        r.p(" [FALHA] Nenhum campo de interesse encontrado.")
        con.close()
        return False

    r.p(f" Campos analisados: {campos}")
    r.p()

    # Cabeçalho
    header = f" {'Ano':<6}" + "".join(f" {c:>12}" for c in campos)
    r.p(header)
    r.p(" " + "-" * len(header))

    for ano in ANOS:
        linha = f" {ano:<6}"
        for campo in campos:
            cur.execute(f"""
                SELECT COUNT(*) FROM observacoes
                WHERE strftime('%Y', data_iso) = ?
                  AND {campo} IS NULL
            """, (str(ano),))
            nulos = cur.fetchone()[0]
            linha += f" {nulos:>12}"
        r.p(linha)

    con.close()
    r.p()
    r.p(" (valores = quantidade de registros com o campo NULO naquele ano)")
    r.p()
    return True


def teste_duplicatas(r):
    r.p("=" * 74)
    r.p(" 6. DUPLICATAS")
    r.p("=" * 74)

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cur.execute("""
        SELECT data_iso, hora_local, COUNT(*) AS n
        FROM observacoes
        GROUP BY data_iso, hora_local
        HAVING n > 1
        ORDER BY n DESC
        LIMIT 20
    """)
    dups = cur.fetchall()

    if not dups:
        r.p(" [OK] Nenhuma duplicata encontrada.")
        con.close()
        r.p()
        return True

    r.p(f" [AVISO] {len(dups)} combinações (data, hora) duplicadas:")
    for data, hora, n in dups:
        r.p(f"   {data} {hora}  ->  {n} registros")

    con.close()
    r.p()
    return False


def teste_faixas(r):
    r.p("=" * 74)
    r.p(" 7. VALORES FORA DE FAIXAS PLAUSÍVEIS")
    r.p("=" * 74)

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    # Verifica tmin e tmax fora das faixas
    testes = [
        ("tmin_real", "tmin fora de [15, 27]", "tmin_real IS NOT NULL AND (tmin_real < 15 OR tmin_real > 27)"),
        ("tmax_real", "tmax fora de [25, 42]", "tmax_real IS NOT NULL AND (tmax_real < 25 OR tmax_real > 42)"),
        ("tmed", "tmed fora de [18, 40]", "tmed IS NOT NULL AND (tmed < 18 OR tmed > 40)"),
        ("tar", "tar fora de [15, 42]", "tar IS NOT NULL AND (tar < 15 OR tar > 42)"),
    ]

    algum_problema = False
    for campo, descricao, condicao in testes:
        try:
            cur.execute(f"SELECT COUNT(*) FROM observacoes WHERE {condicao}")
            n = cur.fetchone()[0]
            if n == 0:
                r.p(f" [OK] {descricao}: 0 registros")
            else:
                r.p(f" [AVISO] {descricao}: {n} registros")
                algum_problema = True
        except sqlite3.OperationalError:
            r.p(f" [SKIP] {campo} não encontrado")

    con.close()
    r.p()
    return not algum_problema


def teste_comparacao_json(r):
    r.p("=" * 74)
    r.p(" 8. COMPARAÇÃO COM JSONs (amostra)")
    r.p("=" * 74)

    # Pega alguns pares para comparar
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    n_testados = 0
    n_diferentes = 0

    for ano in ANOS:
        json_path = DIR_JSON / f"dados_{ano}.json"
        if not json_path.exists():
            continue

        try:
            import json
            with open(json_path, encoding="utf-8") as f:
                regs = json.load(f)
        except Exception:
            continue

        # Testa 5 registros por ano
        for jr in regs[:5]:
            data = normalizar_data(jr.get("Data    (dd/mm/aaaa)"), ano)
            hora = jr.get("Hora local (hh:mm)")
            if not data or not hora:
                continue

            try:
                h, m = hora.split(":")
                hora_norm = f"{int(h):02d}:{int(m):02d}"
            except Exception:
                continue

            cur.execute("""
                SELECT tmin_real, tmax_real, tmed, tar
                FROM observacoes
                WHERE data_iso = ? AND hora_local = ?
            """, (data, hora_norm))
            row = cur.fetchone()
            if row is None:
                continue

            s_tmin, s_tmax, s_tmed, s_tar = row
            j_tmin = para_float(jr.get("Tmin Real (ºC)"))
            j_tmax = para_float(jr.get("Tmáx Real (ºC)"))
            j_tar  = para_float(jr.get("Tar (°C)"))

            difs = []
            for nome, jv, sv in [("tmin", j_tmin, s_tmin),
                                 ("tmax", j_tmax, s_tmax),
                                 ("tar", j_tar, s_tar)]:
                if jv is not None and sv is not None:
                    if abs(jv - sv) > 0.01:
                        difs.append(f"{nome}: json={jv} sqlite={sv}")

            n_testados += 1
            if difs:
                n_diferentes += 1
                r.p(f" [DIF] {data} {hora_norm}: {'; '.join(difs)}")

    con.close()

    if n_testados == 0:
        r.p(" [SKIP] Nenhum registro comparado.")
    elif n_diferentes == 0:
        r.p(f" [OK] {n_testados} registros comparados. Todos batem.")
    else:
        r.p(f" [AVISO] {n_diferentes} de {n_testados} registros divergem.")

    r.p()
    return n_diferentes == 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    r = Reporter(SAIDA_TXT)

    r.p("=" * 74)
    r.p(" VERIFICAÇÃO DE INTEGRIDADE DO BANCO")
    r.p(f" Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    r.p("=" * 74)
    r.p()

    resultados = {}

    if not teste_arquivo(r):
        r.salvar()
        print(f"\nFALHA CRÍTICA. Relatório: {SAIDA_TXT}")
        sys.exit(1)

    resultados["integrity_check"] = teste_integrity_check(r)
    resultados["estrutura"] = teste_estrutura(r)
    resultados["cobertura"] = teste_cobertura(r)
    resultados["nulos"] = teste_nulos(r)
    resultados["duplicatas"] = teste_duplicatas(r)
    resultados["faixas"] = teste_faixas(r)
    resultados["json"] = teste_comparacao_json(r)

    # Síntese
    r.p("=" * 74)
    r.p(" SÍNTESE")
    r.p("=" * 74)
    for teste, ok in resultados.items():
        simbolo = "OK" if ok else "PROBLEMA"
        r.p(f" {teste:<20}  {simbolo}")
    r.p()

    tudo_ok = all(resultados.values())

    if tudo_ok:
        r.p(" STATUS: Banco íntegro. Nenhum problema detectado.")
    else:
        r.p(" STATUS: Um ou mais testes reportaram problema. Verificar acima.")

    r.p("=" * 74)
    r.salvar()

    print(f"\nRelatório salvo em: {SAIDA_TXT}")
    return 0 if tudo_ok else 1


if __name__ == "__main__":
    sys.exit(main())