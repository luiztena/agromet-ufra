def calcular_sensacao_termica(temperatura, umidade, vento=None):
    """
    Calcula a sensação térmica baseada nas condições.
    
    - temperatura: °C
    - umidade: % (0-100)
    - vento: m/s (opcional)
    
    Retorna: sensação térmica em °C
    """
    if temperatura is None or umidade is None:
        return None
    
    # Converte para Fahrenheit para usar a fórmula do Heat Index (padrão NOAA)
    T_f = (temperatura * 9/5) + 32
    
    # Fórmula do Heat Index (NOAA) - válida para T >= 27°C
    if temperatura >= 27:
        hi = calcular_heat_index(T_f, umidade)
        # Converte de volta para Celsius
        sensacao = (hi - 32) * 5/9
        return round(sensacao, 1)
    
    # Wind Chill para temperaturas baixas (improvável em Belém)
    elif temperatura <= 10 and vento is not None and vento > 0:
        sensacao = calcular_wind_chill(temperatura, vento)
        return round(sensacao, 1)
    
    # Temperatura normal (sem ajuste)
    else:
        return round(temperatura, 1)


def calcular_heat_index(T_f, umidade):
    """
    Fórmula do Heat Index da NOAA (National Oceanic and Atmospheric Administration).
    T_f: temperatura em Fahrenheit
    umidade: umidade relativa em %
    Retorna: Heat Index em Fahrenheit
    """
    # Constantes da fórmula de Rothfusz
    hi = (0.5 * (T_f + 61.0 + ((T_f - 68.0) * 1.2) + (umidade * 0.094)))
    
    # Média com a temperatura
    hi = (hi + T_f) / 2
    
    # Se o resultado for menor que 80°F, usa a fórmula simples
    if hi < 80:
        return hi
    
    # Fórmula completa de Rothfusz
    hi = (-42.379 
          + 2.04901523 * T_f 
          + 10.14333127 * umidade 
          - 0.22475541 * T_f * umidade 
          - 6.83783e-3 * T_f**2 
          - 5.481717e-2 * umidade**2 
          + 1.22874e-3 * T_f**2 * umidade 
          + 8.5282e-4 * T_f * umidade**2 
          - 1.99e-6 * T_f**2 * umidade**2)
    
    # Ajustes para condições específicas
    if umidade < 13 and 80 <= T_f <= 112:
        ajuste = ((13 - umidade) / 4) * ((17 - abs(T_f - 95)) / 17)**0.5
        hi -= ajuste
    
    elif umidade > 85 and 80 <= T_f <= 87:
        ajuste = ((umidade - 85) / 10) * ((87 - T_f) / 5)
        hi += ajuste
    
    return round(hi, 1)


def calcular_wind_chill(temperatura, vento):
    """
    Fórmula do Wind Chill (Canadá/EUA).
    temperatura: °C
    vento: m/s
    Retorna: sensação térmica em °C
    """
    # Converte vento de m/s para km/h
    vento_kmh = vento * 3.6
    
    # Fórmula do Wind Chill
    wind_chill = (13.12 
                  + 0.6215 * temperatura 
                  - 11.37 * (vento_kmh ** 0.16) 
                  + 0.3965 * temperatura * (vento_kmh ** 0.16))
    
    return wind_chill


def classificar_sensacao(sensacao):
    """
    Classifica a sensação térmica em categorias descritivas.
    """
    if sensacao is None:
        return "Indisponível"
    
    if sensacao >= 54:
        return "🔥 Perigo extremo"
    elif sensacao >= 41:
        return "⚠️ Perigo"
    elif sensacao >= 32:
        return "🥵 Muito cuidado"
    elif sensacao >= 27:
        return "😓 Cuidado"
    elif sensacao >= 18:
        return "😊 Confortável"
    elif sensacao >= 10:
        return "😐 Fresco"
    elif sensacao >= 0:
        return "🥶 Frio"
    else:
        return "❄️ Muito frio"