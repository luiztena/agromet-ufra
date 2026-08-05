"""
Modulo Agrometeorologico - Calculos de radiacao, energia, evapotranspiracao e fenologia
Baseado nas aulas do Prof. Dr. Paulo Jorge de O. P. de Souza - UFRA
"""
import math
from datetime import datetime


def calcular_fotoperiodo(latitude, data):
    """Calcula a duracao do dia (fotoperiodo) em horas e minutos."""
    dia_juliano = datetime.strptime(data, '%Y-%m-%d').timetuple().tm_yday
    declinacao = 0.409 * math.sin((2 * math.pi / 365) * dia_juliano - 1.39)
    lat_rad = math.radians(latitude)
    omega_s = math.acos(-math.tan(lat_rad) * math.tan(declinacao))
    N_horas = (24 / math.pi) * omega_s
    horas = int(N_horas)
    minutos = int((N_horas - horas) * 60)
    return f"{horas}h {minutos:02d}min"


def calcular_Q0_Ra(latitude, data):
    """Radiação extraterrestre - Ra (FAO) / Q0 (literatura brasileira) (MJ/m²/dia)"""
    dia_juliano = datetime.strptime(data, '%Y-%m-%d').timetuple().tm_yday
    declinacao = 0.409 * math.sin((2 * math.pi / 365) * dia_juliano - 1.39)
    lat_rad = math.radians(latitude)
    omega_s = math.acos(-math.tan(lat_rad) * math.tan(declinacao))
    dr = 1 + 0.033 * math.cos((2 * math.pi / 365) * dia_juliano)
    Gsc = 0.0820  # Constante solar (MJ/m²/min)
    Ra = (24 * 60 / math.pi) * Gsc * dr * (omega_s * math.sin(lat_rad) * math.sin(declinacao) + math.cos(lat_rad) * math.cos(declinacao) * math.sin(omega_s))
    return round(Ra, 1)


def traduzir_codigo_wmo(codigo):
    """Traduz códigos WMO para descrição em português."""
    codigos = {
        0: "Ceu limpo",
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
        80: "Pancadas de chuva",
        81: "Pancadas moderadas",
        82: "Pancadas fortes",
        95: "Trovoada",
        96: "Trovoada com granizo",
        99: "Trovoada severa"
    }
    return codigos.get(codigo, "Indefinido")


def calcular_balanco_completo(temperatura, umidade, data, latitude, Tbase=10, Rs_medido=None, weather_code=None):
    """
    Calcula todos os parametros agrometeorologicos.
    
    Parametros:
    - temperatura: float (C)
    - umidade: float (%)
    - data: string (YYYY-MM-DD)
    - latitude: float
    - Tbase: float (temperatura base para graus-dia, default 10C)
    - Rs_medido: float ou None (radiacao solar medida)
    - weather_code: int ou None (codigo WMO do ECMWF)
    
    Retorna:
    - dict com Ra, Rs, PAR, Rn, Kt, GD, ETo, Fotoperiodo
    """
    
    # ---- Radiacao Extraterrestre (Ra / Q0) ----
    Ra = calcular_Q0_Ra(latitude, data)
    
    # ---- Radiacao Solar Global (Rs) ----
    if Rs_medido is not None:
        Rs = round(Rs_medido, 1)
    else:
        # Estimativa para regioes tropicais umidas
        # Rs = Ra * (0,25 + 0,50 * n/N)
        # Na ausencia de dados de insolacao, adota-se coeficiente representativo
        Rs = round(Ra * 0.55, 1)
    
    # ---- Indice de Claridade (Kt) ----
    Kt = round(Rs / Ra, 2) if Ra > 0 else 0
    
    # Classificacao do ceu: prioriza WMO do ECMWF, depois Kt
    if weather_code is not None:
        condicao_ceu = traduzir_codigo_wmo(weather_code)
        fonte_ceu = "ECMWF (WMO)"
    else:
        # Classificacao adaptada para regiao tropical umida - Belem/PA
        if Kt >= 0.65:
            condicao_ceu = "Ceu limpo"
        elif Kt >= 0.55:
            condicao_ceu = "Poucas nuvens"
        elif Kt >= 0.45:
            condicao_ceu = "Parcialmente nublado"
        elif Kt >= 0.30:
            condicao_ceu = "Nublado"
        else:
            condicao_ceu = "Muito nublado"
        fonte_ceu = "Estimado (Kt)"
    
    # ---- PAR (Radiação Fotossinteticamente Ativa) ----
    PAR = round(Rs * 0.50, 1)
    
    # ---- Radiacao Liquida (Rn) ----
    # Estimativa simplificada para fins didaticos e visualizacao
    Rn = round(Rs * 0.65, 1)
    
    # ---- Fotoperiodo ----
    fotoperiodo = calcular_fotoperiodo(latitude, data)
    
    # ---- Graus-dia ----
    GD = round(temperatura - Tbase, 1)
    if GD < 0:
        GD = 0.0
    
    # ---- ETo - Hargreaves-Samani (FAO-56) ----
    # Escolhido por requerer apenas temperatura e radiacao
    ETo = round(0.0023 * (temperatura + 17.8) * math.sqrt(temperatura - Tbase) * Rs, 2)
    if ETo < 0:
        ETo = 0.0
    
    return {
        "Ra_Q0": {
            "valor": Ra,
            "unidade": "MJ/m²/dia",
            "descricao": "Radiacao Extraterrestre (Ra/Q0)",
            "metodo": "FAO-56 (Calculo astronomico)"
        },
        "Rs": {
            "valor": Rs,
            "unidade": "MJ/m²/dia",
            "descricao": "Radiacao Solar Global",
            "metodo": "Angstrom-Prescott (estimado)" if Rs_medido is None else "Medido"
        },
        "Kt": {
            "valor": Kt,
            "descricao": "Indice de Claridade",
            "condicao": condicao_ceu,
            "fonte": fonte_ceu
        },
        "PAR": {
            "valor": PAR,
            "unidade": "MJ/m²/dia",
            "descricao": "Radiacao Fotossinteticamente Ativa",
            "metodo": "PAR = 0,50 x Rs (FAO)"
        },
        "Rn": {
            "valor": Rn,
            "unidade": "MJ/m²/dia",
            "descricao": "Radiacao Liquida (estimativa simplificada)",
            "metodo": "Rn = 0,65 x Rs (didatico)"
        },
        "fotoperiodo": {
            "valor": fotoperiodo,
            "descricao": "Duracao do dia (Fotoperiodo)"
        },
        "graus_dia": {
            "valor": GD,
            "unidade": "C",
            "descricao": "Graus-dia acumulados",
            "Tbase": Tbase,
            "metodo": f"GD = Tmed - Tbase ({Tbase}C)"
        },
        "ETo": {
            "valor": ETo,
            "unidade": "mm/dia",
            "descricao": "Evapotranspiracao de Referencia",
            "metodo": "Hargreaves-Samani (FAO-56)"
        }
    }