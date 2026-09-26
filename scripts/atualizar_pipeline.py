"""
atualizar_pipeline.py
---------------------
Executa o pipeline completo para um ano:
    1. planilha_para_json.py   (planilha .xlsx -> JSON)
    2. criar_banco.py --force  (recria o banco limpo)
    3. importar_json.py        (JSON -> banco)

Uso:
    python scripts/atualizar_pipeline.py --ano 2026
    python scripts/atualizar_pipeline.py --ano 2026 --planilha "dados_brutos/planilhas/Outra.xlsx"

Por padrão, usa "dados_brutos/planilhas/Dados TAB.xlsx".
"""

import argparse
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SCRIPTS = RAIZ / "scripts"

PLANILHA_PADRAO = "dados_brutos/planilhas/Dados TAB.xlsx"


def rodar(cmd, descricao):
    print()
    print("=" * 60)
    print(f"  {descricao}")
    print("=" * 60)
    print(f"$ {' '.join(str(c) for c in cmd)}")
    print()

    resultado = subprocess.run(cmd, cwd=RAIZ)

    if resultado.returncode != 0:
        print()
        print(f"❌ Erro na etapa: {descricao}")
        print(f"   Código de retorno: {resultado.returncode}")
        sys.exit(resultado.returncode)

    print()
    print(f"✅ {descricao} — OK")


def main():
    parser = argparse.ArgumentParser(
        description="Roda o pipeline completo para um ano."
    )
    parser.add_argument("--ano", required=True, type=int,
                        help="Ano a processar (ex.: 2026).")
    parser.add_argument("--planilha", default=PLANILHA_PADRAO,
                        help=f"Caminho da planilha .xlsx (default: {PLANILHA_PADRAO}).")
    parser.add_argument("--aba", default=None,
                        help="Nome da aba. Default: o próprio ano.")
    args = parser.parse_args()

    ano = args.ano
    aba = args.aba or str(ano)
    planilha = Path(args.planilha)
    json_saida = f"dados_brutos/dados_{ano}.json"

    if not planilha.exists():
        print(f"❌ Planilha não encontrada: {planilha}")
        print(f"   Baixe a planilha do Google Sheets e coloque em: {planilha.parent}/")
        sys.exit(1)

    print("=" * 60)
    print(f"  Pipeline de atualização — ano {ano}")
    print("=" * 60)
    print(f"  Planilha:  {planilha}")
    print(f"  Aba:       {aba}")
    print(f"  JSON:      {json_saida}")
    print()

    # 1. Planilha -> JSON
    rodar(
        [sys.executable, str(SCRIPTS / "planilha_para_json.py"),
         str(planilha), "--aba", aba, "-o", json_saida],
        f"1/3 — Convertendo planilha para JSON (aba {aba})"
    )

    # 2. Recria o banco
    rodar(
        [sys.executable, str(SCRIPTS / "criar_banco.py"), "--force"],
        "2/3 — Recriando o banco do zero"
    )

    # 3. Importa
    rodar(
        [sys.executable, str(SCRIPTS / "importar_json.py"), json_saida],
        f"3/3 — Importando JSON no banco"
    )

    print()
    print("=" * 60)
    print(f"✅ Pipeline do ano {ano} concluído com sucesso.")
    print("=" * 60)
    print()
    print("Valide com:")
    print(f'  sqlite3 banco/ispaam.db "SELECT COUNT(*) FROM observacoes;"')


if __name__ == "__main__":
    main()