import requests
import re
import json
from datetime import datetime
from bs4 import BeautifulSoup

# URL da estação meteorológica da UFRA
URL_ESTACAO = "https://isarh.ufra.edu.br/index.php?option=com_content&view=article&id=176&Itemid=379&lang=en"

# Arquivo JSON local
ARQUIVO_JSON = "Agromet.json"

def baixar_pagina():
    """Baixa o HTML da página da estação."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        resposta = requests.get(URL_ESTACAO, headers=headers, timeout=10)
        resposta.raise_for_status()
        return resposta.text
    except requests.RequestException as e:
        print(f"❌ Erro ao acessar o site: {e}")
        return None

def extrair_dados(html):
    """Extrai os dados meteorológicos do HTML."""
    if not html:
        return None
    
    soup = BeautifulSoup(html, 'html.parser')
    texto = soup.get_text()
    
    # Remove espaços extras e quebras de linha
    texto = ' '.join(texto.split())
    
    # Padrões de regex para cada campo
    padroes = {
        'data': r'OBSERVA[ÇC][ÃA]O DO DIA (\d{2}/\d{2}/\d{4})',
        'temp_09h': r'Temperatura do ar\s*\(instantânea às 09 h\)\s*:\s*([\d,]+)',
        'umidade_09h': r'Umidade relativa do ar\s*\(instantânea às 09 hs\)\s*:\s*([\d,]+)',
        'vento_09h': r'Velocidade do vento\s*\(máxima instantânea [àa]s 09 h\)\s*:\s*([\d,]+)',
        'temp_min': r'Temperatura mínima do ar\s*:\s*([\d,]+)',
        'temp_max_anterior': r'Temperatura máxima do ar\s*\(do dia anterior\)\s*:\s*([\d,]+)',
        'precipitacao': r'Precipita[çc][ãa]o nas 24 h\s*(?:\(leitura as 09 h\))?\s*:\s*([\d,]+)',
        'evaporacao': r'Evapora[çc][ãa]o nas 24 h\s*\(Tanque Classe A[^)]*\)\s*:\s*([\d,]+)',
        'temp_15h': r'Temperatura do ar\s*\(instantânea às 15 h\)\s*:\s*([\d,]+)',
        'umidade_15h': r'Umidade relativa do ar\s*\(instantânea às 15 hs\)\s*:\s*([\d,]+)',
        'vento_15h': r'Velocidade do vento\s*\(máxima instatânea [àa]s 15 h\)\s*:\s*([\d,]+)',
    }
    
    dados = {}
    
    # Extrai cada campo
    for campo, padrao in padroes.items():
        match = re.search(padrao, texto, re.IGNORECASE)
        if match:
            valor = match.group(1)
            if campo == 'data':
                # Converte DD/MM/AAAA para AAAA-MM-DD
                try:
                    data_obj = datetime.strptime(valor, '%d/%m/%Y')
                    dados[campo] = data_obj.strftime('%Y-%m-%d')
                except ValueError:
                    dados[campo] = valor
            else:
                # Converte vírgula para ponto e para float
                try:
                    dados[campo] = float(valor.replace(',', '.'))
                except ValueError:
                    dados[campo] = None
    
    # Extrai observadores e responsável
    match_resp = re.search(r'Docente Responsável\s*:\s*([^|]+)', texto)
    match_obs = re.search(r'Observadores\s*:\s*(.+?)(?:\s*$)', texto)
    
    dados['responsible_teacher'] = match_resp.group(1).strip() if match_resp else "Não identificado"
    dados['observers'] = match_obs.group(1).strip() if match_obs else "Não identificado"
    
    return dados if dados.get('temp_09h') else None

def formatar_para_json(dados_extraidos):
    """Converte os dados extraídos para o formato do Agromet.json."""
    if not dados_extraidos:
        return None
    
    return {
        "date": dados_extraidos.get('data'),
        "temp_09h": dados_extraidos.get('temp_09h'),
        "humidity_09h": dados_extraidos.get('umidade_09h'),
        "wind_09h": dados_extraidos.get('vento_09h'),
        "temp_min": dados_extraidos.get('temp_min'),
        "temp_max_previous_day": dados_extraidos.get('temp_max_anterior'),
        "precipitation_24h": dados_extraidos.get('precipitacao'),
        "evaporation_24h": dados_extraidos.get('evaporacao'),
        "temp_15h": dados_extraidos.get('temp_15h'),
        "humidity_15h": dados_extraidos.get('umidade_15h'),
        "wind_15h": dados_extraidos.get('vento_15h'),
        "responsible_teacher": dados_extraidos.get('responsible_teacher'),
        "observers": dados_extraidos.get('observers')
    }

def carregar_json():
    """Carrega o arquivo JSON existente."""
    try:
        with open(ARQUIVO_JSON, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def salvar_json(dados):
    """Salva os dados no arquivo JSON."""
    with open(ARQUIVO_JSON, 'w', encoding='utf-8') as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
    print(f"✅ Arquivo {ARQUIVO_JSON} atualizado com sucesso!")

def atualizar_dados():
    """Função principal: baixa, extrai e atualiza os dados."""
    print("🌐 Acessando site do ISARH/UFRA...")
    html = baixar_pagina()
    
    if not html:
        return {"status": "erro", "mensagem": "Não foi possível acessar o site"}
    
    print("🔍 Extraindo dados meteorológicos...")
    dados_extraidos = extrair_dados(html)
    
    if not dados_extraidos:
        return {"status": "erro", "mensagem": "Não foi possível extrair os dados"}
    
    novo_registro = formatar_para_json(dados_extraidos)
    
    if not novo_registro or not novo_registro.get('date'):
        return {"status": "erro", "mensagem": "Dados extraídos estão incompletos"}
    
    print(f"📅 Data encontrada: {novo_registro.get('date')}")
    print(f"🌡️ Temperatura 09h: {novo_registro.get('temp_09h')}°C")
    print(f"💧 Umidade 09h: {novo_registro.get('humidity_09h')}%")
    
    # Carrega dados existentes
    dados_existentes = carregar_json()
    
    # Verifica se a data já existe
    data_existente = any(d.get('date') == novo_registro['date'] for d in dados_existentes)
    
    if data_existente:
        print(f"⚠️ Dados da data {novo_registro['date']} já existem. Atualizando registro...")
        # Substitui o registro existente
        dados_existentes = [d for d in dados_existentes if d.get('date') != novo_registro['date']]
    
    # Adiciona o novo registro
    dados_existentes.append(novo_registro)
    
    # Ordena por data
    dados_existentes.sort(key=lambda x: x.get('date', ''))
    
    # Salva
    salvar_json(dados_existentes)
    
    return {
        "status": "sucesso",
        "data": novo_registro['date'],
        "temperatura": novo_registro['temp_09h'],
        "umidade": novo_registro['humidity_09h'],
        "total_registros": len(dados_existentes)
    }

if __name__ == '__main__':
    resultado = atualizar_dados()
    print("\n" + "="*50)
    print(json.dumps(resultado, indent=2, ensure_ascii=False))