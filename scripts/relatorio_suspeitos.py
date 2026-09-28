"""
relatorio_suspeitos.py
-----------------------
Gera um relatório dos valores que estão DENTRO das faixas de validação,
mas que merecem revisão do orientador por estarem fora do comportamento
típico esperado para a região.

NÃO altera o banco. Só lista.

Uso:
    python scripts/relatorio_suspeitos.py
    python scripts/relatorio_suspeitos.py --saida suspeitos.txt
"""

import sqlite3
import argparse
from pathlib import Path
from datetime import datetime


CAMINHO_BANCO = Path("banco/ispaam.db")


# ---------------------------------------------------------------------------
# Regras de "suspeito" — valores dentro da faixa valida, mas fora do padrao
# ---------------------------------------------------------------------------
# (campo, limite_inferior_tipico, limite_superior_tipico, descricao, referencia)
SUSPEITOS = [
    ("ev_mm_dia",  0.0,   8.0,
     "Evaporacao de tanque classe A acima de 8 mm/dia e' incomum na Amazonia",
     "Pereira et al. (2002); FAO-56"),

    ("tar",        20.0,  35.0,
     "Tar fora de 20-35 C e' raro em Belem (clima equatorial)",
     "INMET - Normais Climatologicas 1991-2020"),

    ("tmax",       28.0,  38.0,
     "Tmax fora de 28-38 C e' raro em Belem",
     "INMET - Normais Climatologicas 1991-2020"),

    ("tmin",       19.0,  27.0,
     "Tmin fora de 19-27 C e' raro em Belem",
     "INMET - Normais Climatologicas 1991-2020"),

    ("ur",         60.0,  99.0,
     "UR fora de 60-99% e' incomum em Belem",
     "INMET - Normais Climatologicas 1991-2020"),
]


def consultar(sql, params=()):
    con = sqlite3.connect(CAMINHO_BANCO)
    con.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in con.execute(sql, params).fetchall()]
    finally:
        con.close()


def gerar_relatorio():
    linhas_saida = []
    linhas_saida.append("=" * 78)
    linhas_saida.append(" RELATORIO DE VALORES SUSPEITOS - Estacao UFRA-BEL")
    linhas_saida.append(f" Gerado em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    linhas_saida.append("=" * 78)
    linhas_saida.append("")
    linhas_saida.append(" Este relatorio lista valores que PASSARAM pela validacao")
    linhas_saida.append(" (estao dentro da faixa fisicamente plausivel), mas que")
    linhas_saida.append(" merecem revisao do orientador por estarem fora do")
    linhas_saida.append(" comportamento tipico esperado para a regiao.")
    linhas_saida.append("")
    linhas_saida.append(" NENHUM dado foi alterado. Este e' apenas um relatorio.")
    linhas_saida.append("")

    total_geral = 0

    for campo, mn, mx, descricao, ref in SUSPEITOS:
        linhas_saida.append("")
        linhas_saida.append("-" * 78)
        linhas_saida.append(f" CAMPO: {campo}")
        linhas_saida.append(f" Faixa tipica esperada: {mn} .. {mx}")
        linhas_saida.append(f" Motivo: {descricao}")
        linhas_saida.append(f" Referencia: {ref}")
        linhas_saida.append("-" * 78)

        # Contagem
        contagem = consultar(f"""
            SELECT COUNT(*) AS n FROM observacoes
            WHERE {campo} IS NOT NULL
              AND ({campo} < ? OR {campo} > ?)
        """, (mn, mx))[0]["n"]

        linhas_saida.append(f" Total de casos suspeitos: {contagem}")
        linhas_saida.append("")

        if contagem == 0:
            linhas_saida.append("  [OK] Nenhum caso suspeito.")
            continue

        # Distribuicao por ano
        por_ano = consultar(f"""
            SELECT substr(data_iso, 1, 4) AS ano, COUNT(*) AS n
            FROM observacoes
            WHERE {campo} IS NOT NULL
              AND ({campo} < ? OR {campo} > ?)
            GROUP BY ano ORDER BY ano
        """, (mn, mx))
        linhas_saida.append("  Distribuicao por ano:")
        for r in por_ano:
            linhas_saida.append(f"    {r['ano']}: {r['n']} casos")

        # Amostra dos 10 primeiros
        amostra = consultar(f"""
            SELECT data_iso, hora_local, {campo} AS valor
            FROM observacoes
            WHERE {campo} IS NOT NULL
              AND ({campo} < ? OR {campo} > ?)
            ORDER BY data_iso
            LIMIT 10
        """, (mn, mx))
        linhas_saida.append("")
        linhas_saida.append("  Amostra (10 primeiros casos):")
        for r in amostra:
            linhas_saida.append(
                f"    {r['data_iso']} {r['hora_local']}  {campo}={r['valor']}"
            )

        total_geral += contagem

    linhas_saida.append("")
    linhas_saida.append("=" * 78)
    linhas_saida.append(f" TOTAL DE CASOS SUSPEITOS: {total_geral}")
    linhas_saida.append("=" * 78)
    linhas_saida.append("")
    linhas_saida.append(" PROXIMOS PASSOS:")
    linhas_saida.append("  1. Apresentar este relatorio ao orientador")
    linhas_saida.append("  2. Decidir caso a caso: sao erros de medicao ou eventos reais?")
    linhas_saida.append("  3. Se confirmado erro: ajustar faixa de validacao em")
    linhas_saida.append("     importar_json.py e reimportar")
    linhas_saida.append("  4. Se confirmado evento real: documentar no TCC")
    linhas_saida.append("=" * 78)

    return "\n".join(linhas_saida)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--saida", default="relatorio_suspeitos.txt",
                        help="Arquivo de saida (default: relatorio_suspeitos.txt)")
    args = parser.parse_args()

    if not CAMINHO_BANCO.exists():
        print(f"Banco nao encontrado: {CAMINHO_BANCO}")
        return

    texto = gerar_relatorio()
    print(texto)

    with open(args.saida, "w", encoding="utf-8") as f:
        f.write(texto)
    print(f"\n[OK] Relatorio salvo em: {args.saida}")


if __name__ == "__main__":
    main()