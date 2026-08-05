import json
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
import os
from scraper import atualizar_dados as atualizar_dados_scraper

app = Flask(__name__)
CORS(app)  # Permite requisições de outros domínios

# Coordenadas da estação UFRA
LATITUDE = -1.455016
LONGITUDE = -48.435260
NOME_ESTACAO = "UFRA - Belém/PA"

# Caminho do arquivo JSON
ARQUIVO_JSON = "Agromet.json"

def carregar_dados():
    """Carrega os dados do arquivo JSON."""
    try:
        with open(ARQUIVO_JSON, 'r', encoding='utf-8') as f:
            dados = json.load(f)
        # Corrigir encoding dos observadores se necessário
        for d in dados:
            if 'observers' in d and 'Ã©' in str(d['observers']):
                d['observers'] = d['observers'].encode('latin1').decode('utf-8')
            if 'responsible_teacher' in d and 'Ã©' in str(d['responsible_teacher']):
                d['responsible_teacher'] = d['responsible_teacher'].encode('latin1').decode('utf-8')
        return dados
    except FileNotFoundError:
        print(f"⚠️ Arquivo {ARQUIVO_JSON} não encontrado!")
        return []
    except json.JSONDecodeError:
        print(f"⚠️ Erro ao ler o JSON!")
        return []

@app.route('/')
def index():
    """Página principal com o mapa."""
    return render_template('index.html', 
                         nome_estacao=NOME_ESTACAO,
                         lat=LATITUDE,
                         lng=LONGITUDE)

@app.route('/api/ultima')
def ultima_observacao():
    """Retorna a última observação com dados válidos."""
    dados = carregar_dados()
    if not dados:
        return jsonify({"erro": "Nenhum dado disponível"}), 404
    
    # Procura o último registro que tenha temperatura (não null)
    ultimo = None
    for registro in reversed(dados):
        if registro.get('temp_09h') is not None:
            ultimo = registro
            break
    
    # Se não encontrou nenhum com dados, pega o último mesmo assim
    if ultimo is None:
        ultimo = dados[-1]
    
    return jsonify({
        "data": ultimo.get('date'),
        "temperatura_09h": ultimo.get('temp_09h'),
        "umidade_09h": ultimo.get('humidity_09h'),
        "vento_09h": ultimo.get('wind_09h'),
        "temp_min": ultimo.get('temp_min'),
        "temp_max": ultimo.get('temp_max_previous_day'),
        "precipitacao": ultimo.get('precipitation_24h'),
        "evaporacao": ultimo.get('evaporation_24h'),
        "temp_15h": ultimo.get('temp_15h'),
        "umidade_15h": ultimo.get('humidity_15h'),
        "vento_15h": ultimo.get('wind_15h'),
        "observadores": ultimo.get('observers'),
        "responsavel": ultimo.get('responsible_teacher'),
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "estacao": NOME_ESTACAO
    })

@app.route('/api/atualizar')
def atualizar_dados_estacao():
    """Atualiza os dados buscando no site do ISARH/UFRA."""
    try:
        resultado = atualizar_dados_scraper()
        return jsonify(resultado)
    except Exception as e:
        return jsonify({
            "status": "erro",
            "mensagem": f"Erro ao atualizar: {str(e)}"
        }), 500

@app.route('/api/data/<data>')
def observacao_por_data(data):
    """Retorna a observação de uma data específica (formato: AAAA-MM-DD)."""
    dados = carregar_dados()
    if not dados:
        return jsonify({"erro": "Nenhum dado disponível"}), 404
    
    # Procura o registro da data
    for registro in dados:
        if registro.get('date') == data:
            return jsonify({
                "data": registro.get('date'),
                "temperatura_09h": registro.get('temp_09h'),
                "umidade_09h": registro.get('humidity_09h'),
                "vento_09h": registro.get('wind_09h'),
                "temp_min": registro.get('temp_min'),
                "temp_max": registro.get('temp_max_previous_day'),
                "precipitacao": registro.get('precipitation_24h'),
                "evaporacao": registro.get('evaporation_24h'),
                "temp_15h": registro.get('temp_15h'),
                "umidade_15h": registro.get('humidity_15h'),
                "vento_15h": registro.get('wind_15h'),
                "observadores": registro.get('observers'),
                "responsavel": registro.get('responsible_teacher'),
                "latitude": LATITUDE,
                "longitude": LONGITUDE,
                "estacao": NOME_ESTACAO
            })
    
    return jsonify({"erro": "Data não encontrada"}), 404

@app.route('/api/todas')
def todas_observacoes():
    """Retorna todas as observações (com paginação)."""
    dados = carregar_dados()
    
    # Parâmetros de paginação
    limite = request.args.get('limite', default=100, type=int)
    offset = request.args.get('offset', default=0, type=int)
    
    # Aplicar paginação
    paginado = dados[offset:offset + limite] if dados else []
    
    return jsonify({
        "total": len(dados) if dados else 0,
        "offset": offset,
        "limite": limite,
        "dados": paginado,
        "estacao": {
            "nome": NOME_ESTACAO,
            "latitude": LATITUDE,
            "longitude": LONGITUDE
        }
    })

@app.route('/api/estacao')
def info_estacao():
    """Retorna informações da estação."""
    dados = carregar_dados()
    return jsonify({
        "nome": NOME_ESTACAO,
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "total_registros": len(dados) if dados else 0,
        "primeira_data": dados[0].get('date') if dados else None,
        "ultima_data": dados[-1].get('date') if dados else None
    })

@app.route('/api/resumo')
def resumo_estatistico():
    """Retorna um resumo estatístico dos dados."""
    dados = carregar_dados()
    if not dados:
        return jsonify({"erro": "Sem dados"}), 404
    
    temps = [d.get('temp_09h') for d in dados if d.get('temp_09h') is not None]
    umidades = [d.get('humidity_09h') for d in dados if d.get('humidity_09h') is not None]
    precipitacoes = [d.get('precipitation_24h') for d in dados if d.get('precipitation_24h') is not None]
    
    return jsonify({
        "temperatura": {
            "media": round(sum(temps)/len(temps), 2) if temps else None,
            "minima": min(temps) if temps else None,
            "maxima": max(temps) if temps else None,
            "total": len(temps)
        },
        "umidade": {
            "media": round(sum(umidades)/len(umidades), 2) if umidades else None,
            "minima": min(umidades) if umidades else None,
            "maxima": max(umidades) if umidades else None
        },
        "precipitacao": {
            "total": round(sum(precipitacoes), 2) if precipitacoes else None,
            "media_diaria": round(sum(precipitacoes)/len(precipitacoes), 2) if precipitacoes else None,
            "maxima": max(precipitacoes) if precipitacoes else None
        },
        "total_registros": len(dados)
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)