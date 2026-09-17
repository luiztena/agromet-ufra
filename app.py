"""
Agromet - API Flask para dados meteorológicos da estação UFRA
Consome o JSON normalizado do ISPAAM (duas observações por dia: 09:00 e 15:00).
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
ARQUIVO_JSON = "dados_2026.json"   # <- ajustado para o nome atual do arquivo


# ---------------------------------------------------------------------------
# Helpers de conversão
# ---------------------------------------------------------------------------
def para_float(valor):
    """Converte '33,60' ou '33.60' em float. Retorna None se vazio/inválido."""
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    if isinstance(valor, str):
        s = valor.strip().replace(",", ".")
        if not s:
            return None
        try:
            return float(s)
        except ValueError:
            return None
    return None


def corrigir_encoding(texto):
    """Corrige mojibake comum em nomes (ex.: 'JosÃ©' -> 'José')."""
    if isinstance(texto, str) and "Ã" in texto:
        try:
            return texto.encode("latin1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            return texto
    return texto


def chave_ordenacao(registro):
    """
    Constrói uma chave de ordenação cronológica a partir de 'Data (dd/mm/aaaa)'.
    Como o arquivo só tem dd/mm (sem ano), usamos (mês, dia) como chave.
    Isso garante que o agrupamento e a ordenação fiquem corretos
    mesmo se o JSON não estiver na ordem esperada.

    Se o ano aparecer no campo 'Data' em algum momento (formato dd/mm/aaaa),
    ele é usado como primeiro critério.
    """
    data = registro.get("Data    (dd/mm/aaaa)") or ""
    partes = data.split("/")
    try:
        if len(partes) == 3:  # dd/mm/aaaa
            dia, mes, ano = int(partes[0]), int(partes[1]), int(partes[2])
            return (ano, mes, dia)
        elif len(partes) == 2:  # dd/mm
            dia, mes = int(partes[0]), int(partes[1])
            return (0, mes, dia)
    except (ValueError, IndexError):
        pass
    return (9999, 99, 99)  # registros inválidos vão para o fim


# ---------------------------------------------------------------------------
# Carregamento e agrupamento dos dados
# ---------------------------------------------------------------------------
def carregar_dados():
    """
    Lê o JSON normalizado, ORDENA cronologicamente e agrupa as duas
    observações diárias (09:00 e 15:00) em um único registro por data.
    O resultado mantém o formato que o restante da API e o frontend esperam.
    """
    try:
        with open(ARQUIVO_JSON, "r", encoding="utf-8") as f:
            linhas = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

    # Ponto 4: garante ordem cronológica independente da ordem do arquivo.
    linhas.sort(key=chave_ordenacao)

    por_data = {}

    for linha in linhas:
        data = linha.get("Data    (dd/mm/aaaa)")
        if not data:
            continue
        hora = linha.get("Hora local (hh:mm)")

        reg = por_data.setdefault(data, {
            "date": data,
            "dia_semana": linha.get("  "),
            # 09:00 (protocolo completo)
            "temp_09h": None,
            "humidity_09h": None,
            "wind_09h": None,
            "temp_min": None,
            "temp_max_previous_day": None,
            "precipitation_24h": None,
            "evaporation_24h": None,
            "observers": None,
            "evento_09h": None,
            # 15:00 (protocolo reduzido)
            "temp_15h": None,
            "humidity_15h": None,
            "wind_15h": None,
            "evento_15h": None,
            # metadados
            "protocolo_09h": None,
            "protocolo_15h": None,
        })

        if hora == "09:00":
            reg["temp_09h"]                = para_float(linha.get("Tar (°C)"))
            reg["humidity_09h"]            = para_float(linha.get("UR (%)"))
            reg["wind_09h"]                = linha.get("Direção do vento")
            reg["temp_min"]                = para_float(linha.get("Tmin (°C)"))
            reg["temp_max_previous_day"]   = para_float(linha.get("Tmáx (°C)"))
            reg["precipitation_24h"]       = para_float(linha.get("Prp (mm/dia)"))
            reg["evaporation_24h"]         = para_float(linha.get("Ev (mm/dia)"))
            reg["observers"]               = corrigir_encoding(linha.get("Observadores"))
            reg["evento_09h"]              = linha.get("Evento")
            reg["protocolo_09h"]           = linha.get("protocolo")

        elif hora == "15:00":
            reg["temp_15h"]      = para_float(linha.get("Tar (°C)"))
            reg["humidity_15h"]  = para_float(linha.get("UR (%)"))
            reg["wind_15h"]      = linha.get("Direção do vento")
            reg["evento_15h"]    = linha.get("Evento")
            reg["protocolo_15h"] = linha.get("protocolo")

    # Ponto 4 (reforço): reordena o resultado agrupado cronologicamente.
    resultado = sorted(
        por_data.values(),
        key=lambda r: chave_ordenacao({"Data    (dd/mm/aaaa)": r["date"]}),
    )
    return resultado


# ---------------------------------------------------------------------------
# Montagem da resposta
# ---------------------------------------------------------------------------
def montar_resposta_observacao(registro):
    """Monta o dicionário de resposta padrão a partir de um registro agrupado."""
    temp = registro.get("temp_09h")
    umidade = registro.get("humidity_09h")
    vento = registro.get("wind_09h")
    sensacao = calcular_sensacao_termica(temp, umidade, vento)
    classificacao = classificar_sensacao(sensacao)

    return {
        "data": registro.get("date"),
        "dia_semana": registro.get("dia_semana"),
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
        "evento_09h": registro.get("evento_09h"),
        "evento_15h": registro.get("evento_15h"),
        "observadores": registro.get("observers"),
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

    ultimo = next(
        (r for r in reversed(dados) if r.get("temp_09h") is not None),
        dados[-1]
    )
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
    """
    Lista paginada de observações agrupadas.

    Parâmetros:
      - limite (int, default 100)
      - offset (int, default 0)
      - formato (str, default 'tratado'):
          'tratado' -> registros já convertidos por montar_resposta_observacao
                       (padrão novo, recomendado)
          'bruto'   -> registros agrupados crus (formato intermediário,
                       útil pra debug ou pra quem quer os campos internos
                       como protocolo_09h/protocolo_15h)
    """
    dados = carregar_dados()
    limite = request.args.get("limite", default=100, type=int)
    offset = request.args.get("offset", default=0, type=int)
    formato = request.args.get("formato", default="tratado", type=str).lower()

    paginado = dados[offset:offset + limite] if dados else []

    if formato == "bruto":
        itens = paginado
    else:
        itens = [montar_resposta_observacao(r) for r in paginado]

    return jsonify({
        "total": len(dados) if dados else 0,
        "offset": offset,
        "limite": limite,
        "formato": formato,
        "dados": itens,
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
            temp_max = registro.get("temp_max_previous_day") or temp
            temp_min = registro.get("temp_min")
            umidade = registro.get("humidity_09h")

            if all(v is not None for v in (temp, umidade, temp_max, temp_min)):
                resultado = calcular_balanco_completo(
                    temperatura=temp,
                    temp_max=temp_max,
                    temp_min=temp_min,
                    umidade=umidade,
                    data=data,
                    latitude=LATITUDE,
                    Rs_medido=None,
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

    temps = [d["temp_09h"] for d in dados if d.get("temp_09h") is not None]
    umidades = [d["humidity_09h"] for d in dados if d.get("humidity_09h") is not None]
    precipitacoes = [d["precipitation_24h"] for d in dados if d.get("precipitation_24h") is not None]

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