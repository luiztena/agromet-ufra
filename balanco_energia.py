"""
Modulo Agrometeorologico - Calculos de radiacao, energia, evapotranspiracao e fenologia
Baseado nas aulas do Prof. Dr. Paulo Jorge de O. P. de Souza - UFRA

ETo pelo metodo Penman-Monteith (FAO-56, eq. 56), recomendado para a Amazonia.
"""

import math
from datetime import datetime


# ---------------------------------------------------------------------------
# Constantes da estacao
# ---------------------------------------------------------------------------
ALTITUDE_ESTACAO_M = 10.0      # altitude aproximada da estacao UFRA (m)

# ---------------------------------------------------------------------------
# ATENCAO - VELOCIDADE DO VENTO
# ---------------------------------------------------------------------------
# A serie historica da estacao NAO possui medicao continua de velocidade do
# vento (o campo `direcao_vento` do banco armazena apenas a direcao cardinal,
# ex.: "L", "N", "S"). Como o metodo Penman-Monteith (FAO-56) exige u2, e a
# FAO-56 recomenda adotar u2 = 2,0 m/s na ausencia de dados medidos, usamos
# esse valor como APROXIMACAO PADRAO.
#
# IMPORTANTE: 2,0 m/s NAO representa a velocidade real do vento em Belem.
# E' um valor de referencia que permite estimar ETo com erro tipico de +-10%
# em climas tropicais umidos (Allen et al., 1998, Cap. 3).
# ---------------------------------------------------------------------------
U2_PADRAO = 2.0
U2_ORIGEM = "padrao FAO (sem medicao na estacao)"


# ---------------------------------------------------------------------------
# Funcoes auxiliares (helpers)
# ---------------------------------------------------------------------------
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
    """Radiacao extraterrestre - Ra (FAO) / Q0 (literatura brasileira) (MJ/m²/dia)."""
    dia_juliano = datetime.strptime(data, '%Y-%m-%d').timetuple().tm_yday
    declinacao = 0.409 * math.sin((2 * math.pi / 365) * dia_juliano - 1.39)
    lat_rad = math.radians(latitude)
    omega_s = math.acos(-math.tan(lat_rad) * math.tan(declinacao))
    dr = 1 + 0.033 * math.cos((2 * math.pi / 365) * dia_juliano)
    Gsc = 0.0820  # Constante solar (MJ/m²/min)
    Ra = (24 * 60 / math.pi) * Gsc * dr * (
        omega_s * math.sin(lat_rad) * math.sin(declinacao)
        + math.cos(lat_rad) * math.cos(declinacao) * math.sin(omega_s)
    )
    return round(Ra, 1)


def _pressao_atmosferica(altitude_m):
    """Pressao atmosferica (kPa) em funcao da altitude (FAO-56, eq. 7)."""
    return 101.3 * ((293 - 0.0065 * altitude_m) / 293) ** 5.26


def _constante_psicrometrica(P):
    """Constante psicrometrica gamma (kPa/°C) - FAO-56, eq. 8."""
    return 0.000665 * P


def _declividade_saturacao(T):
    """Delta: declividade da curva de pressao de saturacao (kPa/°C).
    FAO-56, eq. 13."""
    es_T = 0.6108 * math.exp(17.27 * T / (T + 237.3))
    return (4098 * es_T) / ((T + 237.3) ** 2)


def _es_temperatura(T):
    """Pressao de saturacao de vapor para uma temperatura T (kPa).
    FAO-56, eq. 11."""
    return 0.6108 * math.exp(17.27 * T / (T + 237.3))


# ---------------------------------------------------------------------------
# Calculo principal
# ---------------------------------------------------------------------------
def calcular_balanco_completo(temperatura, temp_max, temp_min, umidade, data,
                              latitude, Tbase=10, Rs_medido=None, albedo=0.23,
                              altitude=ALTITUDE_ESTACAO_M, u2=U2_PADRAO):
    """
    Calcula todos os parametros agrometeorologicos (FAO-56).
    Inclui ondas curtas (Rns), ondas longas (Rnl) e ETo por Penman-Monteith.

    Parametros:
    - temperatura: temperatura das 09h (usada para graus-dia)
    - temp_max, temp_min: extremos do dia
    - umidade: UR das 09h (%)
    - data: 'YYYY-MM-DD'
    - latitude: graus decimais
    - Tbase: temperatura base para graus-dia (°C)
    - Rs_medido: radiacao solar medida (MJ/m²/dia) ou None
    - albedo: albedo da superficie (0.23 para grama - FAO)
    - altitude: altitude da estacao (m)
    - u2: velocidade do vento a 2 m (m/s). Se nao houver medicao, usar 2.0
    """

    # ---- Radiacao Extraterrestre (Ra / Q0) ----
    Ra = calcular_Q0_Ra(latitude, data)

    # ---- Radiacao Solar Global (Rs) ----
    if Rs_medido is not None:
        Rs = round(Rs_medido, 1)
    else:
        Rs = round(Ra * 0.55, 1)

    # ---- Indice de Claridade (Kt) ----
    Kt = round(Rs / Ra, 2) if Ra > 0 else 0

    # ---- PAR ----
    PAR = round(Rs * 0.50, 1)

    # ---- Rso (radiacao de ceu claro) ----
    Rso = round(0.75 * Ra, 1)

    # ---- Ondas Curtas Liquidas (Rns) - FAO-56 eq. 38 ----
    Rns = round((1 - albedo) * Rs, 1)

    # ---- Pressoes de vapor ----
    es_tmax = _es_temperatura(temp_max)
    es_tmin = _es_temperatura(temp_min)
    es = (es_tmax + es_tmin) / 2.0            # FAO-56 eq. 12
    ea = (umidade / 100.0) * es               # FAO-56 eq. 17 (aprox. UR media)

    # ---- Ondas Longas Liquidas (Rnl) - FAO-56 eq. 39 ----
    Tmax_K = temp_max + 273.16
    Tmin_K = temp_min + 273.16
    sigma = 4.903e-9  # MJ K^-4 m^-2 day^-1
    termo_temp = (sigma * (Tmax_K ** 4 + Tmin_K ** 4)) / 2.0
    termo_umid = 0.34 - 0.14 * math.sqrt(max(ea, 0))
    if Rso > 0:
        termo_nuvem = 1.35 * (Rs / Rso) - 0.35
    else:
        termo_nuvem = 1.0
    Rnl = round(termo_temp * termo_umid * termo_nuvem, 1)
    if Rnl < 0:
        Rnl = 0.0

    # ---- Radiacao Liquida (Rn) - FAO-56 eq. 40 ----
    Rn = round(Rns - Rnl, 1)

    # ---- Fotoperiodo ----
    fotoperiodo = calcular_fotoperiodo(latitude, data)

    # ---- Amplitude termica ----
    amplitude = temp_max - temp_min
    if amplitude < 0:
        amplitude = 0.0

    # ---- Graus-dia ----
    GD = round(temperatura - Tbase, 1)
    if GD < 0:
        GD = 0.0

    # ---- ETo por Penman-Monteith (FAO-56, eq. 56) ----
    # T e' a media diaria
    Tmed = (temp_max + temp_min) / 2.0

    # Constantes psicrometricas e de saturacao
    P = _pressao_atmosferica(altitude)
    gamma = _constante_psicrometrica(P)
    delta = _declividade_saturacao(Tmed)

    # G (fluxo de calor no solo): para passo diario, FAO-56 recomenda G = 0
    G = 0.0

    # Numerador: 0.408 * delta * (Rn - G) + gamma * (900/(T+273)) * u2 * (es - ea)
    termo_rad = 0.408 * delta * (Rn - G)
    termo_aero = gamma * (900.0 / (Tmed + 273.0)) * u2 * (es - ea)

    # Denominador: delta + gamma * (1 + 0.34 * u2)
    denom = delta + gamma * (1.0 + 0.34 * u2)

    if denom > 0:
        ETo = round((termo_rad + termo_aero) / denom, 2)
    else:
        ETo = 0.0

    if ETo < 0:
        ETo = 0.0

    # ---- Retorno ----
    return {
        "Ra_Q0": {
            "valor": Ra, "unidade": "MJ/m²/dia",
            "descricao": "Radiacao Extraterrestre (Ra/Q0)",
            "metodo": "FAO-56 (Calculo astronomico)"
        },
        "Rs": {
            "valor": Rs, "unidade": "MJ/m²/dia",
            "descricao": "Radiacao Solar Global",
            "metodo": "Angstrom-Prescott (estimado)" if Rs_medido is None else "Medido"
        },
        "Rso": {
            "valor": Rso, "unidade": "MJ/m²/dia",
            "descricao": "Radiacao de ceu claro (Rso)",
            "metodo": "FAO-56 eq. 37 (Rso = 0.75 * Ra)"
        },
        "Kt": {
            "valor": Kt,
            "descricao": "Indice de Claridade (Rs / Ra)",
            "metodo": "0 = nublado, 0.75+ = ceu limpo"
        },
        "PAR": {
            "valor": PAR, "unidade": "MJ/m²/dia",
            "descricao": "Radiacao Fotossinteticamente Ativa",
            "metodo": "PAR = 0,50 x Rs (FAO)"
        },
        "Rns": {
            "valor": Rns, "unidade": "MJ/m²/dia",
            "descricao": "Ondas Curtas Liquidas (Rns)",
            "metodo": f"FAO-56 eq. 38: Rns = (1 - {albedo}) * Rs"
        },
        "Rnl": {
            "valor": Rnl, "unidade": "MJ/m²/dia",
            "descricao": "Ondas Longas Liquidas (Rnl) - PERDA",
            "metodo": "FAO-56 eq. 39 (Stefan-Boltzmann + correcao de umidade e nuvem)",
            "nota": "Rnl entra como PERDA no saldo: Rn = Rns - Rnl"
        },
        "Rn": {
            "valor": Rn, "unidade": "MJ/m²/dia",
            "descricao": "Radiacao Liquida (Rn = Rns - Rnl)",
            "metodo": "FAO-56 eq. 40"
        },
        "fotoperiodo": {
            "valor": fotoperiodo,
            "descricao": "Duracao do dia (Fotoperiodo)"
        },
        "graus_dia": {
            "valor": GD, "unidade": "°C",
            "descricao": "Graus-dia acumulados",
            "Tbase": Tbase,
            "metodo": f"GD = Tmed - Tbase ({Tbase}°C)"
        },
        "ETo": {
            "valor": ETo, "unidade": "mm/dia",
            "descricao": "Evapotranspiracao de Referencia",
            "metodo": "Penman-Monteith (FAO-56, eq. 56)",
            "u2_adotado": u2,
            "u2_origem": U2_ORIGEM,
            "u2_aviso": "Valor de referencia FAO-56; nao representa medicao real da estacao."
        },
        "ETo_diag": {
            "Tmed": round(Tmed, 2),
            "P_kPa": round(P, 2),
            "gamma": round(gamma, 4),
            "delta": round(delta, 4),
            "es": round(es, 3),
            "ea": round(ea, 3),
            "VPD": round(es - ea, 3),
            "u2": u2,
            "u2_origem": U2_ORIGEM,
            "u2_aviso": "2,0 m/s e' valor padrao FAO-56, NAO medicao da estacao.",
            "G": G,
            "metodo_eto": "Penman-Monteith FAO-56 (eq. 56)"
        }
    }