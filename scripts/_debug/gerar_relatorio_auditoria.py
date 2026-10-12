"""
gerar_relatorio_auditoria.py
----------------------------
Gera um TXT com TODAS as linhas suspeitas ou anuladas pela camada de QC.
Uso: python scripts/_debug/gerar_relatorio_auditoria.py
"""
import json
import re
from pathlib import Path
from collections import defaultdict

BASE = Path(__file__).resolve().parent.parent.parent
PASTA = BASE / "dados_brutos"
SAIDA = BASE / "relatorio_auditoria_qc.txt"

# Regras (espelho do importar_json.py)
# (campo_json, nome_legivel, min, max)
REGRAS_FAIXA = [
    ("Tar (°C)",        "tar",        15.0,  45.0),
    ("Tmáx (°C)",       "tmax",       26.0,  45.0),
    ("Tmin (°C)",       "tmin",       18.0,  26.0),
    ("Tmáx Real (ºC)",  "tmax_real",  26.0,  45.0),
    ("Tmin Real (ºC)",  "tmin_real",  18.0,  26.0),
    ("Tméd (ºC)",       "tmed",       10.0,  40.0),
    ("UR (%)",          "ur",          0.0, 100.0),
    ("Prp (mm/dia)",    "prp",         0.0, 500.0),
    ("Ev (mm/dia)",     "ev_mm_dia",   0.0,  20.0),
]


def para_float(valor):
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


def extrair_data_hora(linha):
    """Extrai data_iso e hora do registro."""
    d = linha.get("Data    (dd/mm/aaaa)") or linha.get("Data (dd/mm/aaaa)")
    h = linha.get("Hora local (hh:mm)") or linha.get("Hora local")
    return d, h


# ---------------------------------------------------------------------------
# Processa
# ---------------------------------------------------------------------------
anulacoes = []          # lista de dicts
sinalizacoes = []       # lista de dicts
resumo_por_ano = defaultdict(lambda: {"anulacoes": 0, "sinalizacoes": 0})

for arquivo in sorted(PASTA.glob("dados_*.json")):
    ano = arquivo.stem.split("_")[1]

    with open(arquivo, encoding="utf-8") as f:
        linhas = json.load(f)

    for linha in linhas:
        data, hora = extrair_data_hora(linha)
        if not data or not hora:
            continue

        # ---------- Anulacoes por faixa ----------
        for chave_json, nome_db, mn, mx in REGRAS_FAIXA:
            valor_raw = linha.get(chave_json)
            valor = para_float(valor_raw)
            if valor is None:
                continue
            if not (mn <= valor <= mx):
                anulacoes.append({
                    "data": data,
                    "hora": hora,
                    "campo": nome_db,
                    "valor": valor,
                    "motivo": f"fora da faixa [{mn}, {mx}]",
                    "ano": ano,
                })
                resumo_por_ano[ano]["anulacoes"] += 1

        # ---------- tmin > tmax ----------
        tmin = para_float(linha.get("Tmin (°C)"))
        tmax = para_float(linha.get("Tmáx (°C)"))
        if tmin is not None and tmax is not None and tmin > tmax:
            anulacoes.append({
                "data": data,
                "hora": hora,
                "campo": "tmin/tmax",
                "valor": f"tmin={tmin}, tmax={tmax}",
                "motivo": "tmin > tmax (ambos anulados)",
                "ano": ano,
            })
            resumo_por_ano[ano]["anulacoes"] += 1

        # ---------- Sinalizacao: tmax [26, 27) ----------
        if tmax is not None and 26.0 <= tmax < 27.0:
            tar = para_float(linha.get("Tar (°C)"))
            ur = para_float(linha.get("UR (%)"))
            sinalizacoes.append({
                "data": data,
                "hora": hora,
                "campo": "tmax",
                "valor": tmax,
                "motivo": "tmax entre 26-27 (questionável)",
                "contexto": f"tar={tar}, ur={ur}",
                "ano": ano,
            })
            resumo_por_ano[ano]["sinalizacoes"] += 1

        # ---------- Sinalizacao: tmin (23, 26] ----------
        if tmin is not None and 23.0 < tmin <= 26.0:
            tar = para_float(linha.get("Tar (°C)"))
            ur = para_float(linha.get("UR (%)"))
            sinalizacoes.append({
                "data": data,
                "hora": hora,
                "campo": "tmin",
                "valor": tmin,
                "motivo": "tmin entre 23-26 (atípico)",
                "contexto": f"tar={tar}, ur={ur}",
                "ano": ano,
            })
            resumo_por_ano[ano]["sinalizacoes"] += 1


# ---------------------------------------------------------------------------
# Escreve o relatorio
# ---------------------------------------------------------------------------
with open(SAIDA, "w", encoding="utf-8") as f:
    # Cabecalho
    f.write("=" * 78 + "\n")
    f.write(" RELATORIO DE AUDITORIA QC - Estacao UFRA-BEL\n")
    f.write(" Gerado em: 07/10/2026\n")
    f.write(" Periodo: 2018 a 2026\n")
    f.write("=" * 78 + "\n\n")

    # Sumario
    f.write("SUMARIO\n")
    f.write("-" * 78 + "\n")
    f.write(f"Total de anulacoes:     {len(anulacoes)}\n")
    f.write(f"Total de sinalizacoes:  {len(sinalizacoes)}\n")
    f.write(f"Total de acoes QC:      {len(anulacoes) + len(sinalizacoes)}\n\n")

    # Sumario por ano
    f.write("Por ano:\n")
    f.write(f"{'Ano':<8}{'Anulacoes':<15}{'Sinalizacoes':<15}\n")
    for ano in sorted(resumo_por_ano.keys()):
        r = resumo_por_ano[ano]
        f.write(f"{ano:<8}{r['anulacoes']:<15}{r['sinalizacoes']:<15}\n")
    f.write("\n")

    # ------------------- SECAO 1: ANULACOES -------------------
    f.write("=" * 78 + "\n")
    f.write(" SECAO 1 - ANULACOES (valores viraram NULL)\n")
    f.write("=" * 78 + "\n\n")
    f.write(f"Total: {len(anulacoes)} anulacoes\n\n")

    for i, item in enumerate(anulacoes, start=1):
        f.write(f"[{i:4d}] {item['ano']}-{item['data'][3:5]}-{item['data'][0:2]} {item['hora']}\n")
        f.write(f"      Campo: {item['campo']}\n")
        f.write(f"      Valor: {item['valor']}\n")
        f.write(f"      Motivo: {item['motivo']}\n\n")

    # ------------------- SECAO 2: SINALIZACOES -------------------
    f.write("\n" + "=" * 78 + "\n")
    f.write(" SECAO 2 - SINALIZACOES (valores mantidos, mas sinalizados)\n")
    f.write("=" * 78 + "\n\n")
    f.write(f"Total: {len(sinalizacoes)} sinalizacoes\n\n")

    for i, item in enumerate(sinalizacoes, start=1):
        f.write(f"[{i:4d}] {item['ano']}-{item['data'][3:5]}-{item['data'][0:2]} {item['hora']}\n")
        f.write(f"      Campo: {item['campo']}\n")
        f.write(f"      Valor: {item['valor']}\n")
        f.write(f"      Motivo: {item['motivo']}\n")
        f.write(f"      Contexto: {item['contexto']}\n\n")

print(f"Relatorio salvo em: {SAIDA}")
print(f"Total de anulacoes:    {len(anulacoes)}")
print(f"Total de sinalizacoes: {len(sinalizacoes)}")
print(f"Total de acoes QC:     {len(anulacoes) + len(sinalizacoes)}")