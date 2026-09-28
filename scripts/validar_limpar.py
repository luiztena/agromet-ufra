"""
scripts/validar_limpar.py

Valida e limpa os JSONs de observacoes antes do import pro banco.

Regras aplicadas:
  1. tar fora de [15, 45] °C          -> tar = None
  2. ur  fora de [0, 100] %           -> se > 100: arredonda pra 100
                                         se < 0:   ur = None
  3. tmin > tmax                      -> ambos ficam None (registro inconsistente)
  4. tmin fora de [10, 35] °C         -> tmin = None
  5. tmax fora de [15, 45] °C         -> tmax = None
  6. prp < 0                          -> prp = None
  7. prp > 500 (mm/dia irreal)        -> prp = None
  8. ev_mm_dia < 0                    -> evap = None
  9. hora_local fora de {09:00,15:00} -> registrado no relatorio (nao apaga)

Uso:
    python scripts/validar_limpar.py --dry-run
        -> so relatorio, nao altera nada

    python scripts/validar_limpar.py
        -> aplica limpeza + cria backups

    python scripts/validar_limpar.py --pasta dados_brutos
        -> pasta customizada

    python scripts/validar_limpar.py --pasta dados_brutos dados_2020.json
        -> so um arquivo especifico
"""

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# Regras de sanidade
# ---------------------------------------------------------------------------
# (campo, minimo, maximo, acao_se_fora)
#   acao: 'null'  -> vira None
#         'cap'   -> clampa no limite mais proximo (ex.: 101 -> 100)
#         'skip'  -> ignora (nao mexe)
REGRAS = [
    ("tar",        15.0,  45.0, "null"),
    ("ur",          0.0, 100.0, "cap"),      # > 100 vira 100; < 0 vira None
    ("tmin",       10.0,  35.0, "null"),
    ("tmax",       15.0,  45.0, "null"),
    ("prp",         0.0, 500.0, "null"),
    ("ev_mm_dia",   0.0,  20.0, "null"),
]

HORAS_VALIDAS = {"09:00", "15:00"}


def aplicar_regra(valor, minimo, maximo, acao):
    """Retorna (novo_valor, motivo_alteracao ou None)."""
    if valor is None:
        return valor, None

    try:
        v = float(valor)
    except (TypeError, ValueError):
        return None, f"nao-numerico ({valor!r})"

    if minimo <= v <= maximo:
        return valor, None

    # Fora da faixa
    if acao == "cap":
        # Clampa pro limite mais proximo
        novo = max(minimo, min(maximo, v))
        return novo, f"cap {v} -> {novo}"
    elif acao == "null":
        return None, f"outlier {v} (faixa {minimo}..{maximo}) -> null"
    else:
        return valor, None


def validar_registro(reg):
    """
    Valida um registro (linha) do JSON.
    Retorna (registro_modificado, lista_de_avisos).
    """
    avisos = []

    # --- Horario ---
    hora = reg.get("hora_local")
    if hora not in HORAS_VALIDAS:
        avisos.append(f"hora_local invalida: {hora!r} (data={reg.get('data_iso')})")

    # --- Regras campo a campo ---
    for campo, mn, mx, acao in REGRAS:
        if campo not in reg:
            continue
        valor_original = reg[campo]
        novo, motivo = aplicar_regra(valor_original, mn, mx, acao)
        if motivo:
            reg[campo] = novo
            avisos.append(f"{campo}: {motivo}")

    # --- Regra cruzada: tmin > tmax ---
    tmin = reg.get("tmin")
    tmax = reg.get("tmax")
    if tmin is not None and tmax is not None:
        try:
            if float(tmin) > float(tmax):
                avisos.append(f"tmin ({tmin}) > tmax ({tmax}) -> ambos null")
                reg["tmin"] = None
                reg["tmax"] = None
        except (TypeError, ValueError):
            pass

    return reg, avisos


def processar_arquivo(caminho, dry_run=False):
    """Le, valida, limpa e (se nao for dry-run) salva o JSON."""
    print(f"\n>>> {caminho.name}")

    with open(caminho, "r", encoding="utf-8") as f:
        dados = json.load(f)

    # Aceita tanto lista pura quanto {"dados": [...]}
    if isinstance(dados, dict) and "dados" in dados:
        registros = dados["dados"]
        wrapper = True
    elif isinstance(dados, list):
        registros = dados
        wrapper = False
    else:
        print(f"  [SKIP] formato desconhecido")
        return 0, 0

    total_alterados = 0
    total_avisos = 0
    registros_novos = []

    for reg in registros:
        reg_novo, avisos = validar_registro(reg)
        registros_novos.append(reg_novo)
        if avisos:
            total_alterados += 1
            total_avisos += len(avisos)
            for a in avisos:
                print(f"  - {reg.get('data_iso')}: {a}")

    if total_avisos == 0:
        print("  [OK] nenhum problema encontrado")
        return 0, 0

    print(f"  Resumo: {total_alterados} registros alterados, {total_avisos} avisos")

    if dry_run:
        print("  [DRY-RUN] nada foi salvo")
        return total_alterados, total_avisos

    # Backup do original
    sufixo_backup = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = caminho.with_suffix(f".backup_{sufixo_backup}.json")
    shutil.copy2(caminho, backup)
    print(f"  Backup: {backup.name}")

    # Salva o limpo
    saida = {"dados": registros_novos} if wrapper else registros_novos
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(saida, f, ensure_ascii=False, indent=2)

    print(f"  [OK] arquivo limpo salvo")
    return total_alterados, total_avisos


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("arquivo", nargs="?",
                        help="JSON especifico. Se omitido, processa todos os dados_*.json em dados_brutos/")
    parser.add_argument("--dry-run", action="store_true",
                        help="So mostra o relatorio, nao altera arquivos")
    parser.add_argument("--pasta", default="dados_brutos",
                        help="Pasta onde estao os JSONs (default: dados_brutos)")
    args = parser.parse_args()

    base = Path(__file__).resolve().parent      # .../scripts/
    raiz = base.parent                          # .../agromet-ufra/
    pasta = raiz / args.pasta

    if args.arquivo:
        # Se passou um nome, procura na pasta de dados_brutos
        alvos = [pasta / args.arquivo]
    else:
        alvos = sorted(pasta.glob("dados_*.json"))

    if not alvos:
        print(f"Nenhum JSON encontrado em: {pasta}")
        print(f"Verifique se a pasta existe e contem arquivos 'dados_*.json'.")
        sys.exit(1)

    print("=" * 60)
    print(" VALIDACAO E LIMPEZA DOS JSONs")
    print("=" * 60)
    print(f"Pasta: {pasta}")
    print(f"Modo:  {'DRY-RUN (sem salvar)' if args.dry_run else 'APLICAR'}")
    print(f"Arquivos encontrados: {len(alvos)}")

    total_alt = 0
    total_avisos = 0

    for caminho in alvos:
        if not caminho.exists():
            print(f"\n[SKIP] {caminho.name} nao existe")
            continue
        alt, av = processar_arquivo(caminho, dry_run=args.dry_run)
        total_alt += alt
        total_avisos += av

    print("\n" + "=" * 60)
    print(f" TOTAL: {total_alt} registros alterados, {total_avisos} avisos")
    if args.dry_run:
        print(" Nada foi salvo (modo dry-run)")
    else:
        print(" Backups criados ao lado dos arquivos originais.")
        print(" Proximo passo: python scripts/criar_banco.py --force")
    print("=" * 60)


if __name__ == "__main__":
    main()