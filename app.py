"""
Agromet - API Flask para dados meteorológicos da estação UFRA
Consome o banco SQLite (banco/ispaam.db) com as observações da estação.
"""

import sqlite3
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

# from scraper import atualizar_dados as atualizar_dados_scraper  # descontinuado no IC II
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
CODIGO_ESTACAO = "UFRA-BEL"

# Caminho absoluto para o banco, independente de onde o script é executado
CAMINHO_BANCO = Path(__file__).resolve().parent / "banco" / "ispaam.db"


# ---------------------------------------------------------------------------
# Acesso ao banco
# ---------------------------------------------------------------------------
def consultar_banco(query, params=()):
    """
    Executa uma query no banco e retorna as linhas como lista de dicts.
    Lança RuntimeError se o banco não existir.
    """
    if not CAMINHO_BANCO.exists():
        raise RuntimeError(
            f"Banco não encontrado em {CAMINHO_BANCO}. "
            f"Rode 'python scripts/criar_banco.py' e 'python scripts/importar_json.py'."
        )

    con = sqlite3.connect(CAMINHO_BANCO)
    con.row_factory = sqlite3.Row
    try:
        cur = con.cursor()
        cur.execute(query, params)
        return [dict(row) for row in cur.fetchall()]
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Helpers de conversão
# ---------------------------------------------------------------------------
def data_iso_para_dd_mm(data_iso):
    """'2026-01-01' -> '01/01'."""
    if not data_iso:
        return None
    try:
        _, mes, dia = data_iso.split("-")
        return f"{dia}/{mes}"
    except ValueError:
        return data_iso


def dd_mm_aaaa_para_iso(data_dd_mm_aaaa):
    """
    '14/10/2025' -> '2025-10-14'.
    Aceita também 'dd/mm' e devolve 'mm-dd' (sem ano, formato de sufixo).
    Retorna None se não conseguir converter.
    """
    if not data_dd_mm_aaaa:
        return None
    partes = data_dd_mm_aaaa.split("/")
    if len(partes) == 3:
        dia, mes, ano = partes
        return f"{ano}-{mes.zfill(2)}-{dia.zfill(2)}"
    if len(partes) == 2:
        dia, mes = partes
        return f"{mes.zfill(2)}-{dia.zfill(2)}"  # sufixo, sem ano
    return None


def corrigir_encoding(texto):
    """Corrige mojibake comum em nomes (ex.: 'JosÃ©' -> 'José')."""
    if isinstance(texto, str) and "Ã" in texto:
        try:
            return texto.encode("latin1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            return texto
    return texto


def arredondar(valor, casas=2):
    """Arredonda para N casas decimais. Retorna None se o valor for None."""
    if valor is None:
        return None
    try:
        return round(float(valor), casas)
    except (TypeError, ValueError):
        return valor


def parece_nome(texto):
    """
    Heurística: retorna True se o texto parece nome de pessoa,
    False se parece anotação livre (notas de campo).
    """
    if not texto:
        return False

    texto_lower = texto.lower()

    palavras_chave = [
        "tanque", "chuva", "nublado", "visibilidade", "nuvem", "céu", "ceu",
        "paralisação", "paralisacao", "greve", "termometro", "termômetro",
        "pluviômetro", "pluviometro", "pluv", "evento", "quarentena",
        "capina", "limpeza", "bulbo", "danificado", "perca", "coleta",
        "observador", "manutenção", "manutencao", "esvaziado", "transbordou",
        "lavado", "sujo", "aberto", "quebrou", "automática", "automatica",
        "preenchida", "medias", "médias", "limite", "inferior", "superior",
        "roçagem", "rocagem", "parado", "quebrado",
    ]

    if any(p in texto_lower for p in palavras_chave):
        return False

    if len(texto) > 40:
        return False

    if any(s in texto for s in ["*", "?", "."]):
        return False

    return True


def separar_observadores(valor):
    """
    Separa 'observador' de 'notas'.
    Retorna uma tupla (observador, nota) — cada um pode ser None.
    """
    if not valor:
        return (None, None)

    if parece_nome(valor):
        return (valor, None)
    else:
        return (None, valor)


def agrupar_linha_em_registro(registro, linha):
    """
    Insere os dados de uma linha do banco em um registro agrupado por data.
    Cada data tem um dict com campos de 09:00 e 15:00.
    """
    hora = linha.get("hora_local")

    if hora == "09:00":
        registro["temp_09h"]              = linha.get("tar")
        registro["humidity_09h"]          = linha.get("ur")
        registro["wind_09h"]              = linha.get("direcao_vento")
        registro["temp_min"]              = linha.get("tmin")
        registro["temp_max_previous_day"] = linha.get("tmax")
        registro["precipitation_24h"]     = linha.get("prp")
        registro["evaporation_24h"]       = linha.get("ev_mm_dia")
        registro["observers"]             = corrigir_encoding(linha.get("observadores"))
        registro["evento_09h"]            = linha.get("evento")
        registro["protocolo_09h"]         = linha.get("protocolo")

    elif hora == "15:00":
        registro["temp_15h"]      = linha.get("tar")
        registro["humidity_15h"]  = linha.get("ur")
        registro["wind_15h"]      = linha.get("direcao_vento")
        registro["evento_15h"]    = linha.get("evento")
        registro["protocolo_15h"] = linha.get("protocolo")

    return registro


def novo_registro_agrupado(data_iso, dia_semana):
    """Cria um registro agrupado vazio para uma data."""
    return {
        "date": data_iso_para_dd_mm(data_iso),
        "date_iso": data_iso,
        "dia_semana": dia_semana,
        "temp_09h": None,
        "humidity_09h": None,
        "wind_09h": None,
        "temp_min": None,
        "temp_max_previous_day": None,
        "precipitation_24h": None,
        "evaporation_24h": None,
        "observers": None,
        "evento_09h": None,
        "temp_15h": None,
        "humidity_15h": None,
        "wind_15h": None,
        "evento_15h": None,
        "protocolo_09h": None,
        "protocolo_15h": None,
    }


# ---------------------------------------------------------------------------
# Carregamento dos dados
# ---------------------------------------------------------------------------
def carregar_dados():
    linhas = consultar_banco("""
        SELECT data_iso, dia_semana, hora_local, protocolo,
               tar, ur, direcao_vento,
               tmin, tmax, prp, ev_mm_dia,
               observadores, evento
        FROM observacoes
        ORDER BY data_iso ASC, hora_local ASC
    """)

    por_data = {}
    for linha in linhas:
        data_iso = linha["data_iso"]
        if data_iso not in por_data:
            por_data[data_iso] = novo_registro_agrupado(
                data_iso, linha.get("dia_semana")
            )
        agrupar_linha_em_registro(por_data[data_iso], linha)

    return list(por_data.values())


def carregar_dados_por_ano(ano):
    linhas = consultar_banco("""
        SELECT data_iso, dia_semana, hora_local, protocolo,
               tar, ur, direcao_vento,
               tmin, tmax, prp, ev_mm_dia,
               observadores, evento
        FROM observacoes
        WHERE data_iso LIKE ?
        ORDER BY data_iso ASC, hora_local ASC
    """, (f"{ano}-%",))

    por_data = {}
    for linha in linhas:
        data_iso = linha["data_iso"]
        if data_iso not in por_data:
            por_data[data_iso] = novo_registro_agrupado(
                data_iso, linha.get("dia_semana")
            )
        agrupar_linha_em_registro(por_data[data_iso], linha)

    return list(por_data.values())


def carregar_dados_por_data(data_dd_mm):
    """
    Aceita 'dd/mm' OU 'dd/mm/aaaa'.
    - Com ano (dd/mm/aaaa): filtra exatamente aquela data.
    - Sem ano (dd/mm): pega a data MAIS RECENTE que casa com o sufixo.
    """
    partes = data_dd_mm.split("/")

    if len(partes) == 3:
        dia, mes, ano = partes
        alvo = f"{ano}-{mes.zfill(2)}-{dia.zfill(2)}"
        linhas = consultar_banco("""
            SELECT data_iso, dia_semana, hora_local, protocolo,
                   tar, ur, direcao_vento,
                   tmin, tmax, prp, ev_mm_dia,
                   observadores, evento
            FROM observacoes
            WHERE data_iso = ?
            ORDER BY hora_local ASC
        """, (alvo,))
    elif len(partes) == 2:
        dia, mes = partes
        sufixo = f"-{mes.zfill(2)}-{dia.zfill(2)}"
        linhas = consultar_banco("""
            SELECT data_iso, dia_semana, hora_local, protocolo,
                   tar, ur, direcao_vento,
                   tmin, tmax, prp, ev_mm_dia,
                   observadores, evento
            FROM observacoes
            WHERE data_iso LIKE ?
            ORDER BY data_iso DESC, hora_local ASC
        """, (f"%{sufixo}",))
    else:
        return None

    if not linhas:
        return None

    data_alvo = linhas[0]["data_iso"]
    linhas_mesma_data = [l for l in linhas if l["data_iso"] == data_alvo]

    registro = novo_registro_agrupado(data_alvo, linhas_mesma_data[0].get("dia_semana"))
    for linha in linhas_mesma_data:
        agrupar_linha_em_registro(registro, linha)

    return registro


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

    obs_cru = registro.get("observers")
    observadores, notas = separar_observadores(obs_cru)

    return {
        "data": registro.get("date"),
        "data_iso": registro.get("date_iso"),
        "dia_semana": registro.get("dia_semana"),
        "temperatura_09h": arredondar(temp, 2),
        "umidade_09h": arredondar(umidade, 2),
        "vento_09h": vento,
        "sensacao_termica": arredondar(sensacao, 2),
        "classificacao_sensacao": classificacao,
        "temp_min": arredondar(registro.get("temp_min"), 2),
        "temp_max": arredondar(registro.get("temp_max_previous_day"), 2),
        "precipitacao": arredondar(registro.get("precipitation_24h"), 2),
        "evaporacao": arredondar(registro.get("evaporation_24h"), 2),
        "temp_15h": arredondar(registro.get("temp_15h"), 2),
        "umidade_15h": arredondar(registro.get("humidity_15h"), 2),
        "vento_15h": registro.get("wind_15h"),
        "evento_09h": registro.get("evento_09h"),
        "evento_15h": registro.get("evento_15h"),
        "observadores": observadores,
        "notas": notas,
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "estacao": NOME_ESTACAO,
    }


# ---------------------------------------------------------------------------
# Error handler
# ---------------------------------------------------------------------------
@app.errorhandler(RuntimeError)
def handle_runtime_error(e):
    return jsonify({"erro": str(e)}), 500


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    rows = consultar_banco("""
        SELECT MIN(data_iso) AS min_data, MAX(data_iso) AS max_data
        FROM observacoes
    """)
    info = rows[0] if rows else {}
    data_inicio = info.get("min_data") or "2026-01-01"
    data_fim    = info.get("max_data") or "2026-12-31"

    return render_template(
        "index.html",
        nome_estacao=NOME_ESTACAO,
        lat=LATITUDE,
        lng=LONGITUDE,
        data_inicio=data_inicio,
        data_fim=data_fim,
    )


@app.route("/api/ultima")
def ultima_observacao():
    """Retorna a última observação completa (com temp_09h) disponível."""
    linhas = consultar_banco("""
        SELECT data_iso, dia_semana, hora_local, protocolo,
               tar, ur, direcao_vento,
               tmin, tmax, prp, ev_mm_dia,
               observadores, evento
        FROM observacoes
        WHERE tar IS NOT NULL
        ORDER BY data_iso DESC, hora_local DESC
        LIMIT 2
    """)

    if not linhas:
        return jsonify({"erro": "Nenhum dado disponível"}), 404

    data_alvo = linhas[0]["data_iso"]

    linhas_data = consultar_banco("""
        SELECT data_iso, dia_semana, hora_local, protocolo,
               tar, ur, direcao_vento,
               tmin, tmax, prp, ev_mm_dia,
               observadores, evento
        FROM observacoes
        WHERE data_iso = ?
        ORDER BY hora_local ASC
    """, (data_alvo,))

    registro = novo_registro_agrupado(data_alvo, linhas_data[0].get("dia_semana"))
    for linha in linhas_data:
        agrupar_linha_em_registro(registro, linha)

    return jsonify(montar_resposta_observacao(registro))


@app.route("/api/atualizar")
def atualizar_dados_estacao():
    """DESCONTINUADO no IC II — scraper do ISARH substituido por planilha->JSON->banco."""
    return jsonify({
        "status": "descontinuado",
        "mensagem": "O scraper do ISARH foi descontinuado. Os dados agora vem via planilha -> JSON -> banco."
    }), 410


@app.route("/api/data/<path:data>")
def observacao_por_data(data):
    """Busca uma data no formato 'dd/mm' ou 'dd/mm/aaaa' (ex.: /api/data/14/10/2025)."""
    registro = carregar_dados_por_data(data)
    if not registro:
        return jsonify({"erro": "Data não encontrada"}), 404
    return jsonify(montar_resposta_observacao(registro))


@app.route("/api/todas")
def todas_observacoes():
    """
    Lista paginada de observações agrupadas.

    Parâmetros:
      - limite    (int, default 100)
      - offset    (int, default 0)
      - ano       (int, opcional) — filtra por ano (ex.: 2026)
      - com_dados (bool, default 'false') — se 'true', retorna apenas
                   registros com temperatura das 09h preenchida
      - formato   (str, default 'tratado'):
          'tratado' -> registros convertidos por montar_resposta_observacao
          'bruto'   -> registros agrupados crus (útil pra debug)
    """
    limite = request.args.get("limite", default=100, type=int)
    offset = request.args.get("offset", default=0, type=int)
    ano = request.args.get("ano", type=int)
    formato = request.args.get("formato", default="tratado", type=str).lower()
    com_dados = request.args.get("com_dados", default="false", type=str).lower() == "true"

    if ano:
        dados = carregar_dados_por_ano(ano)
    else:
        dados = carregar_dados()

    # Filtra apenas registros que tem temperatura das 09h preenchida.
    # Util para o grafico (evita retornar dias sem dado no fim do periodo).
    if com_dados:
        dados = [d for d in dados if d.get("temp_09h") is not None]

    paginado = dados[offset:offset + limite] if dados else []

    if formato == "bruto":
        itens = paginado
    else:
        itens = [montar_resposta_observacao(r) for r in paginado]

    return jsonify({
        "total": len(dados) if dados else 0,
        "offset": offset,
        "limite": limite,
        "ano": ano,
        "formato": formato,
        "com_dados": com_dados,
        "dados": itens,
        "estacao": {
            "nome": NOME_ESTACAO,
            "latitude": LATITUDE,
            "longitude": LONGITUDE,
        },
    })


@app.route("/api/estacao")
def info_estacao():
    """Informações sobre a estação. Aceita ?ano=YYYY para filtrar."""
    ano = request.args.get("ano", type=int)

    if ano:
        filtro = "WHERE data_iso LIKE ?"
        params = (f"{ano}-%",)
    else:
        filtro = ""
        params = ()

    rows = consultar_banco(f"""
        SELECT
            COUNT(DISTINCT data_iso) AS total_dias,
            COUNT(*) AS total_observacoes,
            MIN(data_iso) AS primeira_data,
            MAX(data_iso) AS ultima_data
        FROM observacoes
        {filtro}
    """, params)
    info = rows[0] if rows else {}

    return jsonify({
        "nome": NOME_ESTACAO,
        "codigo": CODIGO_ESTACAO,
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "ano": ano,
        "total_dias": info.get("total_dias", 0),
        "total_observacoes": info.get("total_observacoes", 0),
        "primeira_data": info.get("primeira_data"),
        "ultima_data": info.get("ultima_data"),
    })


@app.route("/api/anos")
def anos_disponiveis():
    """Retorna os anos disponíveis no banco e a contagem por ano."""
    rows = consultar_banco("""
        SELECT
            substr(data_iso, 1, 4) AS ano,
            COUNT(DISTINCT data_iso) AS total_dias,
            COUNT(*) AS total_observacoes
        FROM observacoes
        GROUP BY ano
        ORDER BY ano ASC
    """)
    return jsonify({
        "anos": [
            {
                "ano": int(r["ano"]),
                "total_dias": r["total_dias"],
                "total_observacoes": r["total_observacoes"],
            }
            for r in rows
        ]
    })


@app.route("/api/atmosfera")
def condicoes_atmosfericas():
    return jsonify(obter_condicoes_atmosfericas())


@app.route("/api/balanco/<path:data>")
def balanco_energia(data):
    """
    Retorna o balanço de energia para uma data.
    Aceita 'dd/mm' ou 'dd/mm/aaaa' na URL.
    Internamente o cálculo espera 'YYYY-MM-DD'.
    """
    registro = carregar_dados_por_data(data)
    if not registro:
        return jsonify({"erro": "Data não encontrada"}), 404

    temp = registro.get("temp_09h")
    temp_max = registro.get("temp_max_previous_day") or temp
    temp_min = registro.get("temp_min")
    umidade = registro.get("humidity_09h")

    if not all(v is not None for v in (temp, umidade, temp_max, temp_min)):
        return jsonify({"erro": "Dados insuficientes para o cálculo"}), 400

    data_iso = registro.get("date_iso")
    if not data_iso:
        return jsonify({"erro": "Data inválida para cálculo"}), 400

    resultado = calcular_balanco_completo(
        temperatura=temp,
        temp_max=temp_max,
        temp_min=temp_min,
        umidade=umidade,
        data=data_iso,
        latitude=LATITUDE,
        Rs_medido=None,
    )
    return jsonify(resultado)


@app.route("/api/resumo")
def resumo_estatistico():
    """Resumo estatístico. Aceita ?ano=YYYY para filtrar por ano."""
    ano = request.args.get("ano", type=int)

    if ano:
        filtro = "WHERE data_iso LIKE ?"
        params = (f"{ano}-%",)
    else:
        filtro = ""
        params = ()

    rows = consultar_banco(f"""
        SELECT
            AVG(tar)  AS tar_media,
            MIN(tar)  AS tar_min,
            MAX(tar)  AS tar_max,
            AVG(ur)   AS ur_media,
            MIN(ur)   AS ur_min,
            MAX(ur)   AS ur_max,
            SUM(prp)  AS prp_total,
            AVG(prp)  AS prp_media,
            MAX(prp)  AS prp_max,
            COUNT(DISTINCT data_iso) AS total_dias,
            COUNT(*)                 AS total_observacoes
        FROM observacoes
        {filtro}
    """, params)

    info = rows[0] if rows else {}

    return jsonify({
        "ano": ano,
        "temperatura": {
            "media":  arredondar(info.get("tar_media"), 2),
            "minima": arredondar(info.get("tar_min"), 2),
            "maxima": arredondar(info.get("tar_max"), 2),
        },
        "umidade": {
            "media":  arredondar(info.get("ur_media"), 2),
            "minima": arredondar(info.get("ur_min"), 2),
            "maxima": arredondar(info.get("ur_max"), 2),
        },
        "precipitacao": {
            "total":        arredondar(info.get("prp_total"), 2),
            "media_diaria": arredondar(info.get("prp_media"), 2),
            "maxima":       arredondar(info.get("prp_max"), 2),
        },
        "total_dias": info.get("total_dias", 0),
        "total_observacoes": info.get("total_observacoes", 0),
    })


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)