"""
figura_diagnostico_tmin.py
--------------------------
Gera figura com dois painéis:
  (a) Viés mensal de Tmin UFRA × INMET 82191 (2018-2022), com IC 95%
  (b) Viés anual de Tmin, com IC 95% e linha de tendência

Saída: figura_diagnostico_tmin.png (300 dpi, 14x6 polegadas)
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# ---------------------------------------------------------------------------
# Dados (extraídos dos scripts anteriores)
# ---------------------------------------------------------------------------
meses_nomes = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
               "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

# Viés mensal
vies_mensal = {
    "Jan": (-0.583, -0.791, -0.374, 81),
    "Fev": (-0.941, -1.229, -0.652, 76),
    "Mar": (-0.852, -1.084, -0.620, 84),
    "Abr": (-1.167, -1.319, -1.015, 60),
    "Mai": (-1.277, -1.447, -1.108, 53),
    "Jun": (-1.400, -1.583, -1.217, 61),
    "Jul": (-1.353, -1.516, -1.190, 70),
    "Ago": (-1.574, -1.734, -1.414, 84),
    "Set": (-1.548, -1.753, -1.343, 81),
    "Out": (-1.149, -1.335, -0.963, 83),
    "Nov": (-0.848, -1.037, -0.660, 89),
    "Dez": (-0.732, -0.874, -0.591, 114),
}

# Viés anual
vies_anual = {
    2019: (-0.048, -0.286, +0.191, 40),
    2020: (-0.548, -0.653, -0.444, 221),
    2021: (-1.166, -1.247, -1.084, 315),
    2022: (-1.472, -1.569, -1.374, 360),
}

# Estações (para colorir barras)
estacao_mes = {
    "Jan": "chuvosa", "Fev": "chuvosa", "Mar": "chuvosa",
    "Abr": "chuvosa", "Mai": "chuvosa", "Dez": "chuvosa",
    "Jun": "seca",    "Jul": "seca",    "Ago": "seca",
    "Set": "seca",    "Out": "seca",    "Nov": "seca",
}

# ---------------------------------------------------------------------------
# Figura
# ---------------------------------------------------------------------------
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

# --- Painel (a): viés mensal ---
x_meses = np.arange(12)
medias = [vies_mensal[m][0] for m in meses_nomes]
inf    = [vies_mensal[m][1] for m in meses_nomes]
sup    = [vies_mensal[m][2] for m in meses_nomes]
ns     = [vies_mensal[m][3] for m in meses_nomes]

cores = ["#1f77b4" if estacao_mes[m] == "chuvosa" else "#d62728"
         for m in meses_nomes]

# Barras
barras = ax1.bar(x_meses, medias, color=cores, alpha=0.7,
                 edgecolor="black", linewidth=0.8, zorder=2)

# Barras de erro (IC 95%)
yerr_inf = [m - i for m, i in zip(medias, inf)]
yerr_sup = [s - m for m, s in zip(medias, sup)]
ax1.errorbar(x_meses, medias, yerr=[yerr_inf, yerr_sup],
             fmt="none", ecolor="black", capsize=4, linewidth=1.2, zorder=3)

# Linha de referência (viés zero)
ax1.axhline(0, color="gray", linestyle="--", linewidth=1, zorder=1)

# Anotação de N por mês (em cima das barras)
for i, (x, m, n) in enumerate(zip(x_meses, medias, ns)):
    ax1.text(x, m - 0.08, f"n={n}", ha="center", va="top",
             fontsize=7, color="black", zorder=4)

# Rótulos
ax1.set_xticks(x_meses)
ax1.set_xticklabels(meses_nomes, fontsize=10)
ax1.set_ylabel("Viés Tmin (UFRA − INMET) [°C]", fontsize=11)
ax1.set_title("(a) Viés mensal de Tmin — 2018–2022",
              fontsize=12, fontweight="bold")
ax1.grid(axis="y", alpha=0.3, zorder=0)
ax1.set_ylim(-2.0, 0.3)

# Legenda
leg_chuvosa = mpatches.Patch(color="#1f77b4", alpha=0.7,
                             label="Estação chuvosa (dez–mai)")
leg_seca    = mpatches.Patch(color="#d62728", alpha=0.7,
                             label="Estação seca (jun–nov)")
ax1.legend(handles=[leg_chuvosa, leg_seca], loc="lower left", fontsize=9)

# --- Painel (b): viés anual ---
anos = sorted(vies_anual.keys())
medias_a = [vies_anual[a][0] for a in anos]
inf_a    = [vies_anual[a][1] for a in anos]
sup_a    = [vies_anual[a][2] for a in anos]
ns_a     = [vies_anual[a][3] for a in anos]

# Barras
barras_a = ax2.bar(anos, medias_a, color="#8c564b", alpha=0.7,
                   edgecolor="black", linewidth=0.8, width=0.6, zorder=2)

# Barras de erro
yerr_inf_a = [m - i for m, i in zip(medias_a, inf_a)]
yerr_sup_a = [s - m for m, s in zip(medias_a, sup_a)]
ax2.errorbar(anos, medias_a, yerr=[yerr_inf_a, yerr_sup_a],
             fmt="none", ecolor="black", capsize=5, linewidth=1.2, zorder=3)

# Anotação de N por ano
for x, m, n in zip(anos, medias_a, ns_a):
    ax2.text(x, m - 0.08, f"n={n}", ha="center", va="top",
             fontsize=8, color="black", zorder=4)

# Linha de referência (zero)
ax2.axhline(0, color="gray", linestyle="--", linewidth=1, zorder=1)

# Linha de tendência (regressão linear simples)
coef = np.polyfit(anos, medias_a, 1)
x_tend = np.linspace(min(anos) - 0.3, max(anos) + 0.3, 100)
y_tend = np.polyval(coef, x_tend)
ax2.plot(x_tend, y_tend, color="darkred", linestyle="-",
         linewidth=2, label=f"Tendência: {coef[0]:+.2f} °C/ano", zorder=4)

# Rótulos
ax2.set_xticks(anos)
ax2.set_xticklabels([str(a) for a in anos], fontsize=10)
ax2.set_ylabel("Viés Tmin (UFRA − INMET) [°C]", fontsize=11)
ax2.set_title("(b) Viés anual de Tmin — tendência temporal",
              fontsize=12, fontweight="bold")
ax2.grid(axis="y", alpha=0.3, zorder=0)
ax2.set_ylim(-2.0, 0.4)
ax2.legend(loc="lower left", fontsize=10)

# Ajuste final
plt.tight_layout()
plt.savefig("figura_diagnostico_tmin.png", dpi=300, bbox_inches="tight")
print("Figura salva: figura_diagnostico_tmin.png")
plt.show()