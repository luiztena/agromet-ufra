import requests
from datetime import datetime

# Coordenadas da UFRA
LAT = -1.455016
LNG = -48.435260

def obter_condicoes_atmosfericas():
    """
    Busca dados atmosféricos em tempo real da API Open-Meteo (ECMWF).
    Mesma fonte usada pelo Windy.
    """
    url = "https://api.open-meteo.com/v1/forecast"
    
    params = {
        "latitude": LAT,
        "longitude": LNG,
        "current": [
            "wind_speed_10m",
            "wind_direction_10m",
            "wind_gusts_10m",
            "precipitation",
            "rain",
            "showers",
            "weather_code",
            "cloud_cover",
            "relative_humidity_2m",
            "temperature_2m"
        ],
        "daily": [
            "temperature_2m_max",
            "temperature_2m_min"
        ],
        "timezone": "America/Belem",
        "forecast_days": 1
    }
    
    try:
        resposta = requests.get(url, params=params, timeout=10)
        resposta.raise_for_status()
        dados = resposta.json()
        
        current = dados.get('current', {})
        daily = dados.get('daily', {})
        
        # Velocidade do vento em m/s (Open-Meteo retorna km/h)
        velocidade_kmh = current.get('wind_speed_10m', 0)
        velocidade_ms = round(velocidade_kmh / 3.6, 1)
        
        # Direção do vento
        direcao_graus = current.get('wind_direction_10m', 0)
        direcao_cardeal = graus_para_cardeal(direcao_graus)
        
        # Rajada
        rajada_kmh = current.get('wind_gusts_10m', 0)
        rajada_ms = round(rajada_kmh / 3.6, 1)
        
        # Chuva
        precipitacao = current.get('precipitation', 0)
        chuva = current.get('rain', 0)
        chovendo = precipitacao > 0 or chuva > 0
        
        # Código do tempo (WMO)
        codigo_tempo = current.get('weather_code', 0)
        descricao_tempo = traduzir_codigo_tempo(codigo_tempo)
        
        # Cobertura de nuvens
        nuvens = current.get('cloud_cover', 0)
        
        # Temperaturas máximas e mínimas do dia (ECMWF)
        temp_max = daily.get('temperature_2m_max', [None])[0] if daily.get('temperature_2m_max') else None
        temp_min = daily.get('temperature_2m_min', [None])[0] if daily.get('temperature_2m_min') else None
        
        return {
            "status": "sucesso",
            "vento": {
                "velocidade": velocidade_ms,
                "velocidade_kmh": velocidade_kmh,
                "direcao_graus": direcao_graus,
                "direcao_cardeal": direcao_cardeal,
                "rajada": rajada_ms,
                "rajada_kmh": rajada_kmh,
                "fonte": "ECMWF (Open-Meteo)"
            },
            "chuva": {
                "chovendo": chovendo,
                "intensidade": "fraca" if precipitacao < 2.5 else "moderada" if precipitacao < 10 else "forte",
                "precipitacao_mm": precipitacao,
                "fonte": "ECMWF (Open-Meteo)"
            },
            "ceu": {
                "descricao": descricao_tempo,
                "codigo_wmo": codigo_tempo,
                "nuvens_pct": nuvens
            },
            "temperatura": {
                "atual": current.get('temperature_2m'),
                "umidade": current.get('relative_humidity_2m'),
                "maxima": temp_max,
                "minima": temp_min
            },
            "atualizado_em": datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
            "fonte_dados": "Open-Meteo (ECMWF) - Modelo Global"
        }
        
    except requests.RequestException as e:
        return {
            "status": "erro",
            "mensagem": f"Erro ao buscar dados atmosféricos: {str(e)}"
        }


def graus_para_cardeal(graus):
    """Converte graus de direção do vento para pontos cardeais em português."""
    direcoes = [
        'N', 'NNE', 'NE', 'ENE',
        'E', 'ESE', 'SE', 'SSE',
        'S', 'SSO', 'SO', 'OSO',
        'O', 'ONO', 'NO', 'NNO'
    ]
    
    traducao = {
        'N': 'Norte',
        'NNE': 'Norte-Nordeste',
        'NE': 'Nordeste',
        'ENE': 'Leste-Nordeste',
        'E': 'Leste',
        'ESE': 'Leste-Sudeste',
        'SE': 'Sudeste',
        'SSE': 'Sul-Sudeste',
        'S': 'Sul',
        'SSO': 'Sul-Sudoeste',
        'SO': 'Sudoeste',
        'OSO': 'Oeste-Sudoeste',
        'O': 'Oeste',
        'ONO': 'Oeste-Noroeste',
        'NO': 'Noroeste',
        'NNO': 'Norte-Noroeste'
    }
    
    indice = round(graus / 22.5) % 16
    sigla = direcoes[indice]
    return traducao.get(sigla, sigla)


def traduzir_codigo_tempo(codigo):
    """Traduz códigos WMO para descrição em português."""
    codigos = {
        0: "Céu limpo",
        1: "Parcialmente nublado",
        2: "Nublado",
        3: "Encoberto",
        45: "Nevoeiro",
        48: "Nevoeiro com geada",
        51: "Garoa leve",
        53: "Garoa moderada",
        55: "Garoa intensa",
        61: "Chuva fraca",
        63: "Chuva moderada",
        65: "Chuva forte",
        71: "Neve fraca",
        73: "Neve moderada",
        75: "Neve forte",
        80: "Pancadas de chuva",
        81: "Pancadas moderadas",
        82: "Pancadas fortes",
        95: "Trovoada",
        96: "Trovoada com granizo",
        99: "Trovoada severa"
    }
    return codigos.get(codigo, "Indefinido")