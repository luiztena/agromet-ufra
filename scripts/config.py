"""
config.py
---------
Configuração centralizada de caminhos do projeto, versão ADAPTATIVA.

O que faz:
  - Descobre a raiz do projeto automaticamente.
  - Procura cada arquivo crítico em múltiplos lugares plausíveis.
  - Reporta onde achou (ou não achou).
  - Fornece funções que os scripts usam para acessar arquivos e pastas.

Uso:
    from config import (
        BASE_PROJETO, DB_PATH, PLANILHA_XLSX,
        INMET_82191_D, INMET_82191_H, INMET_A201_H,
        DIR_JSON, DIR_RELATORIOS, DIR_IMAGENS,
        json_do_ano, verificar,
    )

Rodar direto para ver o relatório:
    python scripts/config.py
"""

from pathlib import Path
import sys


# ===========================================================================
# 1. RAIZ DO PROJETO
# ===========================================================================
BASE_PROJETO = Path(__file__).resolve().parent.parent


# ===========================================================================
# 2. PASTAS PRINCIPAIS
# ===========================================================================
DIR_SCRIPTS    = BASE_PROJETO / "scripts"
DIR_DADOS      = BASE_PROJETO / "dados_brutos"
DIR_BANCO      = BASE_PROJETO / "banco"
DIR_RELATORIOS = BASE_PROJETO / "relatorios"
DIR_IMAGENS    = DIR_RELATORIOS / "imagens"
DIR_PLANILHA   = BASE_PROJETO / "planilha"


# ===========================================================================
# 3. FUNÇÃO DE BUSCA ADAPTATIVA
# ===========================================================================

def _procurar(nome_arquivo, pastas_candidatas):
    """
    Procura um arquivo em uma lista de pastas candidatas.
    Retorna o Path se encontrar, None se não encontrar.

    Se encontrar em múltiplos lugares, avisa no stderr e usa o primeiro.
    """
    encontrados = []
    for pasta in pastas_candidatas:
        if pasta is None:
            continue
        candidato = Path(pasta) / nome_arquivo
        if candidato.exists() and candidato.is_file():
            encontrados.append(candidato)

    if len(encontrados) > 1:
        print(
            f"[config] AVISO: '{nome_arquivo}' encontrado em {len(encontrados)} lugares. "
            f"Usando o primeiro:\n"
            + "\n".join(f"  - {p}" for p in encontrados),
            file=sys.stderr,
        )

    return encontrados[0] if encontrados else None


# ===========================================================================
# 4. ARQUIVOS CRÍTICOS — BUSCA ADAPTATIVA
# ===========================================================================

# --- Banco de dados ---------------------------------------------------------
DB_PATH = _procurar("ispaam.db", [
    DIR_BANCO,
    BASE_PROJETO / "banco",
    BASE_PROJETO,                       # caso esteja na raiz (improvável)
    BASE_PROJETO / "dados_brutos",
])


# --- Planilha principal da UFRA ---------------------------------------------
PLANILHA_XLSX = _procurar("Dados TAB.xlsx", [
    DIR_DADOS / "planilhas",            # estrutura atual (plural)
    DIR_DADOS / "planilha",             # caso renomeie para singular
    DIR_PLANILHA,                       # caso mova para raiz/planilha/
    DIR_PLANILHA / "INMET",
    DIR_DADOS,
    BASE_PROJETO,
])


# --- Dados do INMET (entrada) -----------------------------------------------
# Cada estação procura em todos os lugares plausíveis.

INMET_82191_D = _procurar("dados_82191_D_2018-01-01_2025-12-31.csv", [
    DIR_PLANILHA / "INMET",             # estrutura atual
    DIR_PLANILHA,                       # estrutura antiga
    DIR_PLANILHA / "INMET" / "Dados de entrada",   # se separar
    BASE_PROJETO,
])

INMET_82191_H = _procurar("dados_82191_H_2018-01-01_2025-12-31.csv", [
    DIR_PLANILHA / "INMET",
    DIR_PLANILHA,
    DIR_PLANILHA / "INMET" / "Dados de entrada",
    BASE_PROJETO,
])

INMET_A201_H = _procurar("dados_A201_H_2018-01-01_2025-12-31.csv", [
    DIR_PLANILHA / "INMET",
    DIR_PLANILHA,
    DIR_PLANILHA / "INMET" / "Dados de entrada",
    BASE_PROJETO,
])


# --- Diretório dos JSONs ----------------------------------------------------
# Aceita JSONs em dados_brutos/ (atual) ou em subpasta.

def _detectar_dir_json():
    """Retorna a pasta que contém os JSONs gerados."""
    candidatas = [
        DIR_DADOS,                          # dados_brutos/*.json (atual)
        DIR_DADOS / "json",                 # se mover para subpasta
        DIR_DADOS / "planilha",             # se juntar com a planilha
        BASE_PROJETO,                       # fallback
    ]
    for pasta in candidatas:
        if pasta and (pasta / "dados_2018.json").exists():
            return pasta
    # Fallback silencioso: retorna dados_brutos mesmo sem ter os JSONs
    return DIR_DADOS


DIR_JSON = _detectar_dir_json()


# --- Diretório de relatórios -----------------------------------------------
# Garante que existe (só cria pasta vazia; não move nada)

DIR_RELATORIOS.mkdir(parents=True, exist_ok=True)
DIR_IMAGENS.mkdir(parents=True, exist_ok=True)


# ===========================================================================
# 5. ANOS DISPONÍVEIS
# ===========================================================================
ANOS = list(range(2018, 2027))


# ===========================================================================
# 6. ESTAÇÕES (Belém)
# ===========================================================================
MESES_CHUVOSA = {12, 1, 2, 3, 4, 5}
MESES_SECA    = {6, 7, 8, 9, 10, 11}

NOMES_MES = {
    1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Set", 10: "Out", 11: "Nov", 12: "Dez",
}


# ===========================================================================
# 7. HELPERS PARA USO NOS SCRIPTS
# ===========================================================================

def json_do_ano(ano):
    """
    Retorna o Path do JSON do ano solicitado.
    Se o arquivo não existir, retorna None.
    """
    caminho = DIR_JSON / f"dados_{ano}.json"
    return caminho if caminho.exists() else None


def verificar(verbose=True):
    """
    Verifica se todos os arquivos críticos foram encontrados.
    Retorna True se tudo OK, False se algum faltar.

    Se verbose=True, imprime um relatório.
    """
    if not verbose:
        return all([
            DB_PATH is not None,
            PLANILHA_XLSX is not None,
            INMET_82191_D is not None,
            INMET_82191_H is not None,
            INMET_A201_H is not None,
        ])

    print("=" * 74)
    print(" RELATÓRIO DE CAMINHOS")
    print("=" * 74)

    print("\n Pastas:")
    print(f"   Base do projeto:  {BASE_PROJETO}")
    print(f"   scripts/:         {DIR_SCRIPTS}  "
          f"[{'OK' if DIR_SCRIPTS.exists() else 'FALTA'}]")
    print(f"   dados_brutos/:    {DIR_DADOS}  "
          f"[{'OK' if DIR_DADOS.exists() else 'FALTA'}]")
    print(f"   planilha/:        {DIR_PLANILHA}  "
          f"[{'OK' if DIR_PLANILHA.exists() else 'FALTA'}]")
    print(f"   relatorios/:      {DIR_RELATORIOS}  "
          f"[{'OK' if DIR_RELATORIOS.exists() else 'FALTA'}]")
    print(f"   banco/:           {DIR_BANCO}  "
          f"[{'OK' if DIR_BANCO.exists() else 'FALTA'}]")

    print("\n Arquivos críticos:")

    def linha(nome, path):
        if path and Path(path).exists():
            print(f"   {nome:<22} [OK]    {path}")
        else:
            print(f"   {nome:<22} [FALTA]")

    linha("ispaam.db", DB_PATH)
    linha("Dados TAB.xlsx", PLANILHA_XLSX)
    linha("dados_82191_D...", INMET_82191_D)
    linha("dados_82191_H...", INMET_82191_H)
    linha("dados_A201_H...", INMET_A201_H)

    print("\n JSONs:")
    print(f"   pasta detectada:  {DIR_JSON}")
    for ano in ANOS:
        j = json_do_ano(ano)
        if j:
            print(f"   dados_{ano}.json      [OK]    {j}")
        else:
            print(f"   dados_{ano}.json      [FALTA]  (esperado em {DIR_JSON})")

    print("\n Pastas de saída:")
    print(f"   relatorios/            "
          f"[{'OK' if DIR_RELATORIOS.exists() else 'FALTA'}]")
    print(f"   relatorios/imagens/    "
          f"[{'OK' if DIR_IMAGENS.exists() else 'FALTA'}]")

    print("\n" + "=" * 74)

    # Retorno
    tudo_ok = all([
        DB_PATH is not None,
        PLANILHA_XLSX is not None,
        INMET_82191_D is not None,
        INMET_82191_H is not None,
        INMET_A201_H is not None,
        all(json_do_ano(a) for a in ANOS),
    ])

    if tudo_ok:
        print(" STATUS: Todos os arquivos críticos foram encontrados.")
    else:
        print(" STATUS: Alguns arquivos NÃO foram encontrados.")
        print("         Verifique as seções marcadas com [FALTA] acima.")

    print("=" * 74)
    return tudo_ok


# ===========================================================================
# 8. EXECUÇÃO DIRETA
# ===========================================================================

if __name__ == "__main__":
    ok = verificar(verbose=True)
    sys.exit(0 if ok else 1)