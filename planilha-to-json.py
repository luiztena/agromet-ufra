import csv
import json

# Configurações de arquivos
arquivo_csv = 'dados.csv'
arquivo_json = 'dados.json'

print("Lendo o arquivo CSV e convertendo...")

try:
    # Abre o arquivo CSV (ajuste o encoding para 'utf-8' ou 'latin-1' se necessário)
    with open(arquivo_csv, mode='r', encoding='utf-8-sig') as f_csv:
        # Lê o CSV automaticamente mapeando as linhas para dicionários (usando o cabeçalho)
        leitor_csv = csv.DictReader(f_csv)
        
        # Converte as linhas para uma lista do Python
        dados = list(leitor_csv)

    # Escreve o arquivo JSON formatado
    with open(arquivo_json, mode='w', encoding='utf-8') as f_json:
        json.dump(dados, f_json, indent=4, ensure_ascii=False)

    print(f"Sucesso! O arquivo '{arquivo_json}' foi gerado perfeitamente.")

except FileNotFoundError:
    print(f"Erro: O arquivo '{arquivo_csv}' não foi encontrado na pasta. Verifique o nome.")
except Exception as e:
    print(f"Ocorreu um erro inesperado: {e}")
