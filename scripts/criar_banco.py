"""
criar_banco.py
--------------
Cria o banco ispaam.db com o schema completo e insere os dados iniciais:
- Estação UFRA-BEL
- Dicionário de variáveis canônicas

Uso:
    python scripts/criar_banco.py
    python scripts/criar_banco.py --force   (recria, apaga tudo)
"""

import sqlite3
import sys
import argparse
from pathlib import Path
from datetime import datetime


# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
CAMINHO_BANCO = Path("banco/ispaam.db")

ESTACAO = {
    "codigo":      "UFRA-BEL",
    "nome":        "UFRA - Belém/PA",
    "latitude":    -1.455016,
    "longitude":   -48.435260,
    "altitude":    None,
    "operadora":   "ISPAAM",
    "data_inicio": None,
    "data_fim":    None,
    "observacoes": "Estação meteorológica do ISPAAM/UFRA em Belém/PA.",
}

# Dicionário canônico de variáveis
# (codigo, nome, unidade, cf_standard_name, wmo_code, descricao)
VARIAVEIS = [
    ("tar",          "Temperatura do ar (bulbo seco)", "°C",  "air_temperature",                 None, "Temperatura do ar no momento da observação."),
    ("th2o_ev",      "Temperatura do bulbo úmido",     "°C",  "wet_bulb_temperature",            None, "Temperatura do bulbo úmido evaporado."),
    ("tmax",         "Temperatura máxima",             "°C",  "air_temperature",                 None, "Temperatura máxima acumulada desde a observação anterior."),
    ("tmin",         "Temperatura mínima",             "°C",  "air_temperature",                 None, "Temperatura mínima acumulada desde a observação anterior."),
    ("tmax_real",    "Temperatura máxima corrigida",   "°C",  None,                              None, "Temperatura máxima após correção."),
    ("tmin_real",    "Temperatura mínima corrigida",   "°C",  None,                              None, "Temperatura mínima após correção."),
    ("tmed",         "Temperatura média",              "°C",  None,                              None, "Temperatura média do período."),
    ("ur",           "Umidade relativa",               "%",   "relative_humidity",               None, "Umidade relativa do ar."),
    ("estu",         "esTU",                           None,  None,                              None, "Variável psicrométrica (a confirmar definição)."),
    ("ea",           "Pressão parcial de vapor",       "hPa", "water_vapor_partial_pressure",    None, "Pressão parcial de vapor d'água."),
    ("es",           "Pressão de saturação",           "hPa", "saturation_water_vapor_pressure", None, "Pressão de saturação do vapor d'água."),
    ("direcao_vento","Direção do vento",               None,  "wind_from_direction",             None, "Direção predominante do vento (N, NE, L, SE, S, SO, O, NO)."),
    ("u2",           "Velocidade do vento a 2 m",      "m/s", "wind_speed",                      None, "Velocidade do vento a 2 m de altura."),
    ("prp",          "Precipitação",                   "mm",  "precipitation_amount",            None, "Precipitação acumulada."),
    ("soma_prp",     "Soma de precipitação",           "mm",  "precipitation_amount",            None, "Soma acumulada de precipitação."),
    ("pluv_alt",     "Pluviômetro alternativo",        "ml",  None,                              None, "Leitura do pluviômetro alternativo."),
    ("ev_mm",        "Evaporação do tanque (bruta)",   "mm",  "water_evaporation_amount",        None, "Leitura bruta do tanque de evaporação."),
    ("ev_mm_ast",    "Evaporação (mm)*",               "mm",  None,                              None, "Evaporação em campo alternativo."),
    ("ev_mm_dia",    "Evaporação calculada",           "mm",  "water_evaporation_amount",        None, "Evaporação diária calculada."),
    ("tanque",       "Tanque",                         None,  None,                              None, "Informação sobre o tanque."),
    ("patm",         "Pressão atmosférica",            "hPa", "air_pressure",                    None, "Pressão atmosférica ao nível da estação."),
    ("evento",       "Evento meteorológico",           None,  None,                              None, "Código de evento (chuva, nublado, etc.)."),
    ("visibilidade", "Visibilidade",                   None,  "visibility_in_air",               None, "Visibilidade horizontal."),
    ("nuvem",        "Nuvem",                          None,  "cloud_type",                      None, "Tipo de nuvem predominante."),
    ("cobertura_ceu","Cobertura do céu",               None,  "cloud_area_fraction",             None, "Fração do céu coberta por nuvens."),
    ("observadores", "Observadores",                   None,  None,                              None, "Nome(s) do(s) observador(es)."),
]


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
    versao       INTEGER PRIMARY KEY,
    aplicado_em  TEXT NOT NULL,
    descricao    TEXT
);

CREATE TABLE IF NOT EXISTS estacoes (
    id            INTEGER PRIMARY KEY,
    codigo        TEXT UNIQUE NOT NULL,
    nome          TEXT NOT NULL,
    latitude      REAL NOT NULL,
    longitude     REAL NOT NULL,
    altitude      REAL,
    operadora     TEXT,
    data_inicio   TEXT,
    data_fim      TEXT,
    observacoes   TEXT
);

CREATE TABLE IF NOT EXISTS variaveis (
    id               INTEGER PRIMARY KEY,
    codigo           TEXT UNIQUE NOT NULL,
    nome             TEXT NOT NULL,
    unidade          TEXT,
    cf_standard_name TEXT,
    wmo_code         TEXT,
    descricao        TEXT
);

CREATE TABLE IF NOT EXISTS importacoes (
    id              INTEGER PRIMARY KEY,
    arquivo         TEXT NOT NULL,
    estacao_codigo  TEXT,
    importado_em    TEXT NOT NULL,
    total_registros INTEGER,
    observacoes     TEXT
);

CREATE TABLE IF NOT EXISTS observacoes (
    id              INTEGER PRIMARY KEY,
    estacao_id      INTEGER NOT NULL,
    importacao_id   INTEGER,

    data_iso        TEXT NOT NULL,
    hora_local      TEXT NOT NULL,
    hora_utc        TEXT,
    dia_semana      TEXT,
    protocolo       TEXT,

    tar             REAL,
    th2o_ev         REAL,
    tmax            REAL,
    tmin            REAL,
    tmax_real       REAL,
    tmin_real       REAL,
    tmed            REAL,

    ur              REAL,
    estu            REAL,
    ea              REAL,
    es              REAL,

    direcao_vento   TEXT,
    u2              REAL,

    prp             REAL,
    soma_prp        REAL,
    pluv_alt        REAL,
    ev_mm           REAL,
    ev_mm_ast       REAL,
    ev_mm_dia       REAL,
    tanque          REAL,

    patm            REAL,

    evento          TEXT,
    visibilidade    TEXT,
    nuvem           TEXT,
    cobertura_ceu   TEXT,
    observadores    TEXT,

    tipo_tar        TEXT,
    tipo_ur         TEXT,

    FOREIGN KEY (estacao_id)    REFERENCES estacoes(id),
    FOREIGN KEY (importacao_id) REFERENCES importacoes(id),
    UNIQUE(estacao_id, data_iso, hora_local)
);

CREATE INDEX IF NOT EXISTS idx_obs_estacao   ON observacoes(estacao_id);
CREATE INDEX IF NOT EXISTS idx_obs_data      ON observacoes(data_iso);
CREATE INDEX IF NOT EXISTS idx_obs_hora      ON observacoes(hora_local);
CREATE INDEX IF NOT EXISTS idx_obs_protocolo ON observacoes(protocolo);

CREATE TABLE IF NOT EXISTS qc_flags (
    id            INTEGER PRIMARY KEY,
    observacao_id INTEGER NOT NULL,
    variavel      TEXT,
    regra         TEXT NOT NULL,
    severidade    TEXT NOT NULL,
    descricao     TEXT,
    FOREIGN KEY (observacao_id) REFERENCES observacoes(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_qc_obs   ON qc_flags(observacao_id);
CREATE INDEX IF NOT EXISTS idx_qc_regra ON qc_flags(regra);
"""


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------
def criar_banco(forcar: bool = False):
    if CAMINHO_BANCO.exists():
        if not forcar:
            print(f"Banco já existe em {CAMINHO_BANCO}.")
            print("Use --force para recriar (apaga tudo).")
            sys.exit(0)
        print(f"Removendo banco existente: {CAMINHO_BANCO}")
        CAMINHO_BANCO.unlink()

    CAMINHO_BANCO.parent.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(CAMINHO_BANCO)
    con.execute("PRAGMA foreign_keys = ON;")
    cur = con.cursor()

    print(f"Criando schema em {CAMINHO_BANCO}...")
    cur.executescript(SCHEMA)

    cur.execute(
        "INSERT INTO schema_version (versao, aplicado_em, descricao) VALUES (?, ?, ?)",
        (1, datetime.now().isoformat(timespec="seconds"), "Schema inicial"),
    )

    cur.execute(
        """
        INSERT INTO estacoes (codigo, nome, latitude, longitude, altitude,
                              operadora, data_inicio, data_fim, observacoes)
        VALUES (:codigo, :nome, :latitude, :longitude, :altitude,
                :operadora, :data_inicio, :data_fim, :observacoes)
        """,
        ESTACAO,
    )
    print(f"  Estação inserida: {ESTACAO['codigo']}")

    for v in VARIAVEIS:
        cur.execute(
            """
            INSERT INTO variaveis (codigo, nome, unidade, cf_standard_name, wmo_code, descricao)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            v,
        )
    print(f"  {len(VARIAVEIS)} variáveis inseridas.")

    con.commit()
    con.close()

    print(f"\nBanco criado: {CAMINHO_BANCO}")
    print(f"Tabelas: schema_version, estacoes, variaveis, importacoes, observacoes, qc_flags")


def main():
    parser = argparse.ArgumentParser(description="Cria o banco ispaam.db.")
    parser.add_argument("--force", action="store_true", help="Recria o banco mesmo se existir.")
    args = parser.parse_args()
    criar_banco(forcar=args.force)


if __name__ == "__main__":
    main()