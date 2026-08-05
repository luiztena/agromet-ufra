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


def calcular_balanco_completo(temperatura, temp_max, temp_min, umidade, data, latitude, Tbase=10, Rs_medido=None):
    """
    Calcula todos os parametros agrometeorologicos.
    
    Parametros:
    - temperatura: float (C) - temperatura media ou representativa (ex: T09h)
    - temp_max: float (C) - temperatura maxima do dia
    - temp_min: float (C) - temperatura minima do dia
    - umidade: float (%)
    - data: string (YYYY-MM-DD)
    - latitude: float
    - Tbase: float (temperatura base para graus-dia, default 10C)
    - Rs_medido: float ou None (radiacao solar medida)
    
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
    
    # ---- PAR (Radiação Fotossinteticamente Ativa) ----
    PAR = round(Rs * 0.50, 1)
    
    # ---- Radiacao Liquida (Rn) ----
    # Estimativa simplificada para fins didaticos e visualizacao
    Rn = round(Rs * 0.65, 1)
    
    # ---- Fotoperiodo ----
    fotoperiodo = calcular_fotoperiodo(latitude, data)
    
    # ---- Amplitude termica diaria ----
    amplitude = temp_max - temp_min
    if amplitude < 0:
        amplitude = 0.0
    
    # ---- Graus-dia ----
    GD = round(temperatura - Tbase, 1)
    if GD < 0:
        GD = 0.0
    
    # ---- ETo - Hargreaves-Samani (FAO-56) ----
    # ATENCAO: A formula original usa Ra (radiacao extraterrestre), NAO Rs
    # A amplitude termica (Tmax-Tmin) atua como proxy da transmissividade atmosferica
    # O coeficiente 0,0023 ja inclui a conversao de unidades (calor latente de vaporizacao)
    # Resultado em mm/dia
    if amplitude > 0:
        ETo = round(0.0023 * (temperatura + 17.8) * math.sqrt(amplitude) * Ra, 2)
    else:
        ETo = 0.0
    
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
            "descricao": "Indice de Claridade"
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
            "metodo": "Hargreaves-Samani (FAO-56) - usa Ra e amplitude termica"
        }
    }