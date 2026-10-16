# Metadados da Estação UFRA-BEL

**Localização:** Campus UFRA, Belém-PA
**Altitude:** 10 m
**Coordenadas:** [latitude, longitude]
**Início de operação:** [data]

---

## Histórico de sensores

| Período | Sensor Tmin | Sensor Tmáx | Sensor Tar | Observação |
|---------|-------------|-------------|------------|------------|
| 2018–2022 | funcional | funcional | funcional | operação normal |
| 07/2023–12/2024 | **falha** | funcional | funcional | termômetro de mínima quebrado |
| 01/2025–presente | funcional | funcional | funcional | sensor substituído |

---

## Sítio

- **Camada 1 (abrigo, ~10 m):** grama
- **Camada 2 (entorno macro, ~50–200 m):** árvores
- **Camada 3 (~1,5 km):** rio

Descrição do sítio em ordem crescente de escala:
1. Grama no espaço imediato do abrigo
2. Árvores no entorno macro do campus
3. Rio a aproximadamente 1,5 km de distância

---

## Referências INMET

**Estação 82191 (convencional):**
- Latitude: -1.4358°
- Longitude: -48.4372°
- Altitude: ~7–10 m
- Tipo: convencional, 3 leituras/dia

**Estação A201 (automática):**
- Latitude: ~-1.43°
- Longitude: ~-48.43°
- Altitude: 21,2 m
- Tipo: automática, horária
- Localização: mesmo jardim de observação que a 82191

---

## Análise de viés

### Tmin (2018–2022, antes da falha)

- Viés de −1,09 °C contra INMET 82191 (IC 95% [−1,15, −1,03])
- Sazonalidade: seca −1,30 °C vs chuvosa −0,88 °C (p < 10⁻¹²)
- Tendência: −0,49 °C/ano entre 2019 e 2022
- Hipótese física: resfriamento noturno do sítio (grama + árvores + rio)

### Tmax (2018–2025)

- Viés de +0,009 °C contra INMET 82191 (IC 95% [−0,045, +0,063])
- p-valor = 0,74 (não significativo)
- r = 0,725, Willmott d = 0,846
- Sazonalidade fraca: chuvosa +0,105 °C vs seca −0,079 °C
- Oscilação interanual: −0,22 °C (2021) a +0,34 °C (2019)
- Sem tendência temporal sistemática

---

## Falha instrumental documentada

**Sensor de mínima (Tmin):**

- Quebra: 23 de julho de 2023
- Recuperação parcial: 11 de agosto de 2023 (1 dia)
- Recuperação definitiva: janeiro de 2025
- Período de lacuna: 23/07/2023 a 12/2024
- Dado perdido: irrecuperável

**Causa provável:**
Quebra física do termômetro de álcool (sensor de mínima), que é um sensor
distinto do termistor de temperatura instantânea (Tar) e do termômetro de
máxima (Tmáx).

**Evidência:**
- JSONs brutos mostram `Tmin = null` a partir de 23/07/2023
- Sensores de `Tar` e `Tmáx` permaneceram funcionais
- Cobertura mensal de Tmin cai de ~80% na estação chuvosa para ~25% em outubro

---

## Recomendações operacionais

1. **Para uso em 2018–2022:** aplicar correção aditiva de +1,09 °C em Tmin
   para homogeneizar com INMET 82191.
2. **Para 2023–2024:** não usar Tmin. Documentar como lacuna.
3. **Para 2025 em diante:** validar novamente após confirmação de troca de
   sensor.
4. **Para Tmax:** usar sem correção. Validada contra INMET 82191.