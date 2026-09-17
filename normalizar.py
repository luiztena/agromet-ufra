"""
normalizar.py
-------------
Normaliza o JSON de observações do ISPAAM:
- Substitui "" (ou strings só com espaços) por null.
- Adiciona campo "protocolo" baseado na hora local:
    09:00 -> "completo"
    15:00 -> "reduzido"
- Não remove nenhum campo. Preserva a ordem original das chaves.

Uso:
    python normalizar.py dados_2026.json
    python normalizar.py dados_2026.json -o dados_2026_norm.json

Se -o não for passado, sobrescreve o próprio arquivo (com backup automático).
"""

import json
import sys
import shutil
import argparse
from pathlib import Path


# Mapeamento hora local -> protocolo
PROTOCOLO_POR_HORA = {
    "09:00": "completo",
    "15:00": "reduzido",
}


def esta_vazio(valor):
    """Considera vazio: None ou string só com espaços."""
    if valor is None:
        return True
    if isinstance(valor, str) and valor.strip() == "":
        return True
    return False


def normalizar_arquivo(caminho_entrada: Path, caminho_saida: Path):
    with open(caminho_entrada, encoding="utf-8") as f:
        dados = json.load(f)

    if not isinstance(dados, list):
        raise ValueError("O JSON não é uma lista de objetos.")

    total = len(dados)
    n_nulos = 0
    n_protocolos = 0
    horas_desconhecidas = set()

    for item in dados:
        # 1) "" -> null
        for chave, valor in item.items():
            if esta_vazio(valor):
                item[chave] = None
                n_nulos += 1

        # 2) Adiciona "protocolo" baseado na hora local
        hora = item.get("Hora local (hh:mm)")
        if hora in PROTOCOLO_POR_HORA:
            item["protocolo"] = PROTOCOLO_POR_HORA[hora]
            n_protocolos += 1
        else:
            item["protocolo"] = None
            if hora is not None:
                horas_desconhecidas.add(hora)

    # Backup se for sobrescrever
    if caminho_entrada.resolve() == caminho_saida.resolve():
        backup = caminho_entrada.with_suffix(".json.bak")
        shutil.copy2(caminho_entrada, backup)
        print(f"Backup criado: {backup}")

    with open(caminho_saida, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=4)

    # Relatório
    print(f"\nArquivo: {caminho_entrada.name}")
    print(f"  Registros processados : {total}")
    print(f"  Valores virados null  : {n_nulos}")
    print(f"  Protocolos atribuídos : {n_protocolos}")
    if horas_desconhecidas:
        print(f"  Horas não mapeadas    : {sorted(horas_desconhecidas)}")
    print(f"  Saída                 : {caminho_saida}")


def main():
    parser = argparse.ArgumentParser(description="Normaliza JSON de observações do ISPAAM.")
    parser.add_argument("entrada", help="Arquivo JSON de entrada.")
    parser.add_argument("-o", "--saida", help="Arquivo JSON de saída (padrão: sobrescreve entrada).")
    args = parser.parse_args()

    entrada = Path(args.entrada)
    if not entrada.exists():
        print(f"Arquivo não encontrado: {entrada}")
        sys.exit(1)

    saida = Path(args.saida) if args.saida else entrada
    normalizar_arquivo(entrada, saida)


if __name__ == "__main__":
    main()