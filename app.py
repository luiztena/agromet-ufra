"""
Agromet - API Flask para dados meteorológicos da estação UFRA
"""
import json
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

from scraper import atualizar_dados as atualizar_dados_scraper
from atmosfera import obter_condicoes_atmosfericas
from sensacao import calcular_sensacao_termica, classificar_sensacao
from balanco_energia import calcular_balanco_completo

# ---------------------------------------------------------------------------
# Configuração da aplicação
# ---------------------------------------------------------------------------
app = Flask(__name__)
CORS(app)

LATITUDE = -1.455016
LONGITUDE = -48.435260
NOME_ESTACAO = "UFRA - Belém/PA"
ARQUIVO_JSON = "Agromet.json"


# ---------------------------------------------------------------------------
# Funções auxiliares
# ---------------------------------------------------------------------------
def carregar_dados():
    """Lê o arquivo JSON de observações e corrige encoding quando necessário."""
    try:
        with open(ARQUIVO_JSON, "r", encoding="utf-8") as f:
            dados = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

    for registro in dados:
        if "observers" in registro and "Ã©" in str(registro["observers"]):
            registro["observers"] = registro["observers"].encode("latin1").decode("utf-8")
        if "responsible_teacher" in registro and "Ã©" in str(registro["responsible_teacher"]):
            registro["responsible_teacher"] = registro["responsible_teacher"].encode("latin1").decode("utf-8")

    return dados


def montar_resposta_observacao(registro):
    """Monta o dicionário de resposta padrão a partir de um registro."""
    temp = registro.get("temp_09h")
    umidade = registro.get("humidity_09h")
    vento = registro.get("wind_09h")
    sensacao = calcular_sensacao_termica(temp, umidade, vento)
    classificacao = classificar_sensacao(sensacao)

    return {
        "data": registro.get("date"),
        "temperatura_09h": temp,
        "umidade_09h": umidade,
        "vento_09h": vento,
        "sensacao_termica": sensacao,
        "classificacao_sensacao": classificacao,
        "temp_min": registro.get("temp_min"),
        "temp_max": registro.get("temp_max_previous_day"),
        "precipitacao": registro.get("precipitation_24h"),
        "evaporacao": registro.get("evaporation_24h"),
        "temp_15h": registro.get("temp_15h"),
        "umidade_15h": registro.get("humidity_15h"),
        "vento_15h": registro.get("wind_15h"),
        "observadores": registro.get("observers"),
        "responsavel": registro.get("responsible_teacher"),
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "estacao": NOME_ESTACAO,
    }


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template(
        "index.html",
        nome_estacao=NOME_ESTACAO,
        lat=LATITUDE,
        lng=LONGITUDE,
    )


@app.route("/api/ultima")
def ultima_observacao():
    dados = carregar_dados()
    if not dados:
        return jsonify({"erro": "Nenhum dado disponível"}), 404

    ultimo = next((r for r in reversed(dados) if r.get("temp_09h") is not None), dados[-1])
    return jsonify(montar_resposta_observacao(ultimo))


@app.route("/api/atualizar")
def atualizar_dados_estacao():
    try:
        resultado = atualizar_dados_scraper()
        return jsonify(resultado)
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


@app.route("/api/data/<data>")
def observacao_por_data(data):
    dados = carregar_dados()
    if not dados:
        return jsonify({"erro": "Nenhum dado disponível"}), 404

    for registro in dados:
        if registro.get("date") == data:
            return jsonify(montar_resposta_observacao(registro))

    return jsonify({"erro": "Data não encontrada"}), 404


@app.route("/api/todas")
def todas_observacoes():
    dados = carregar_dados()
    limite = request.args.get("limite", default=100, type=int)
    offset = request.args.get("offset", default=0, type=int)
    paginado = dados[offset:offset + limite] if dados else []

    return jsonify({
        "total": len(dados) if dados else 0,
        "offset": offset,
        "limite": limite,
        "dados": paginado,
        "estacao": {
            "nome": NOME_ESTACAO,
            "latitude": LATITUDE,
            "longitude": LONGITUDE,
        },
    })


@app.route("/api/estacao")
def info_estacao():
    dados = carregar_dados()
    return jsonify({
        "nome": NOME_ESTACAO,
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "total_registros": len(dados) if dados else 0,
        "primeira_data": dados[0].get("date") if dados else None,
        "ultima_data": dados[-1].get("date") if dados else None,
    })


@app.route("/api/atmosfera")
def condicoes_atmosfericas():
    return jsonify(obter_condicoes_atmosfericas())


@app.route("/api/balanco/<data>")
def balanco_energia(data):
    """Retorna o balanço de energia para uma data específica."""
    dados = carregar_dados()
    if not dados:
        return jsonify({"erro": "Nenhum dado disponível"}), 404

    for registro in dados:
        if registro.get("date") == data:
            temp = registro.get("temp_09h")
            temp_max = registro.get("temp_max_previous_day") or registro.get("temp_max") or temp
            temp_min = registro.get("temp_min")
            umidade = registro.get("humidity_09h")
            
            if temp is not None and umidade is not None and temp_max is not None and temp_min is not None:
                resultado = calcular_balanco_completo(
                    temperatura=temp,
                    temp_max=temp_max,
                    temp_min=temp_min,
                    umidade=umidade,
                    data=data,
                    latitude=LATITUDE,
                    Rs_medido=None
                )
                return jsonify(resultado)
            else:
                return jsonify({"erro": "Dados insuficientes para o cálculo"}), 400

    return jsonify({"erro": "Data não encontrada"}), 404


@app.route("/api/resumo")
def resumo_estatistico():
    dados = carregar_dados()
    if not dados:
        return jsonify({"erro": "Sem dados"}), 404

    temps = [d.get("temp_09h") for d in dados if d.get("temp_09h") is not None]
    umidades = [d.get("humidity_09h") for d in dados if d.get("humidity_09h") is not None]
    precipitacoes = [d.get("precipitation_24h") for d in dados if d.get("precipitation_24h") is not None]

    return jsonify({
        "temperatura": {
            "media": round(sum(temps) / len(temps), 2) if temps else None,
            "minima": min(temps) if temps else None,
            "maxima": max(temps) if temps else None,
        },
        "umidade": {
            "media": round(sum(umidades) / len(umidades), 2) if umidades else None,
            "minima": min(umidades) if umidades else None,
            "maxima": max(umidades) if umidades else None,
        },
        "precipitacao": {
            "total": round(sum(precipitacoes), 2) if precipitacoes else None,
            "media_diaria": round(sum(precipitacoes) / len(precipitacoes), 2) if precipitacoes else None,
            "maxima": max(precipitacoes) if precipitacoes else None,
        },
        "total_registros": len(dados),
    })


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)