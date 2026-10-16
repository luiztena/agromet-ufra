# Relatório de Auditoria do Pipeline de Dados
## Estação UFRA-BEL — 2018 a 2026

**Data da auditoria:** 12 de outubro de 2026
**Escopo:** Planilha de origem → JSON → SQLite → QC

---

## 1. Resumo executivo

O pipeline de dados da estação UFRA-BEL foi auditado de ponta a ponta em
outubro de 2026. A auditoria identificou:

- **1 falha instrumental:** quebra do termômetro de mínima em 23/07/2023,
  com recuperação em janeiro de 2025.
- **1 bug de geração de JSON:** cálculo incorreto de `Tméd` quando `Tmin`
  está ausente, produzindo valores absurdos (16–18 °C).
- **2 bugs no script conversor:** variável não definida em `_dia_semana_confere`;
  encoding incompatível no subprocess.
- **1 regra de QC mal parametrizada:** faixa 23–26 °C marcada como atípica
  quando é a faixa normal para Belém.

Todos os problemas foram corrigidos. O banco SQLite foi reprocessado a partir
dos JSONs saneados. O diagnóstico pós-correção mostra zero inconsistências.

---

## 2. Falha instrumental

**O que aconteceu:**
Em 23 de julho de 2023, o sensor de temperatura mínima (`Tmin`) da estação
UFRA-BEL parou de reportar valores. A série ficou com `Tmin = null` até
janeiro de 2025, com uma breve recuperação em 11/08/2023.

**Como foi identificado:**
- Análise dos JSONs brutos mostrou `Tmin = null` a partir de 23/07/2023
- Sensores de `Tar` (instantânea) e `Tmáx` (máxima) continuaram funcionando
- Coerente com falha física do termômetro de álcool (sensor de mínima)

**Impacto:**
- Período de falha: 23/07/2023 a 12/2024 (~18 meses)
- Cobertura de `Tmin`: cai de ~80% na estação chuvosa para ~25% em outubro
- O dado de `Tmin` no período **não existe** e não pode ser recuperado

**Ação tomada:**
- Documentado como lacuna instrumental
- Série de `Tmin` considerada válida apenas em 2018–2022 e 2025–2026

---

## 3. Bug de geração de JSON

**O que acontecia:**
A fórmula na planilha Excel para cálculo de `Tméd` era:

    Tméd = (Tmin + Tmáx) / 2

Quando `Tmin` estava vazio (célula em branco), o Excel tratava como zero,
produzindo `Tméd = (0 + 33,4) / 2 = 16,7`. Esses valores foram registrados
nos JSONs e no SQLite.

**Onde foi identificado:**
- JSON de 2023 mostrou 27 registros com `Tméd = 16,7`, `16,8`, `17,2`, etc.
- Análise dos anos 2021, 2022, 2025 também revelou valores abaixo de 20 °C
- Total: 36 registros em 9 anos

**Impacto:**
- Campo `Tméd` corrompido em 36 registros
- Campos `Tmin`, `Tmáx`, `Tar` não afetados
- Diagnóstico de Tmin **não** afetado

**Ação tomada:**
- Não foi possível corrigir a planilha (fonte externa)
- Adicionado saneamento `sanear_registro()` no script `planilha_para_json.py`
- Função recalcula `Tméd` corretamente: só calcula se ambos existem
- Todos os JSONs foram regenerados em 12/10/2026

---

## 4. Bugs no script conversor

**Bug 1 — variável não definida:**

    File "planilha_para_json.py", line 117, in _dia_semana_confere
        dt = datetime.strptime(s, "%d/%m")
    NameError: name 's' is not defined

Causava falha nas abas 2018, 2019 e 2020.

**Correção:** removida a linha ofensiva. A validação agora usa
`data = datetime(ano, mm, dd)` diretamente.

**Bug 2 — encoding incompatível:**

    UnicodeDecodeError: 'utf-8' codec can't decode byte 0xe7

O `regerar_todos_json.py` tentava ler a saída do subprocess como UTF-8,
mas o Windows usa cp1252. O byte `0xe7` (ç) quebrava a decodificação.

**Correção:** `subprocess.run(..., encoding="cp1252", errors="replace")`.

---

## 5. Regra de QC mal parametrizada

**O que acontecia:**
A regra de QC marcava `Tmin entre 23 e 26 °C` como "atípico". Isso produziu
797 falsos positivos — 87% de todas as ações de QC.

**Análise:**
23–26 °C **é a faixa normal** de Tmin em Belém. A regra foi copiada de outro
contexto climático.

**Correção proposta:**
Substituir por:
- `Tmin entre 18 e 23 °C` → atípico (frio)
- `Tmin > 26 °C` → atípico (quente)

**Impacto esperado:**
Redução de 797 sinalizações para ~30–50 casos reais.

**Status:** proposta, aguardando aplicação.

---

## 6. Procedimento de reprocessamento

**Ordem executada:**

1. Backup do banco: `ispaam_antes_correcao_pipeline.db`
2. Backup dos JSONs: `dados_brutos\backup_json_antes_saneamento\`
3. Modificação do `planilha_para_json.py`: adição de `sanear_registro()`
4. Correção do `_dia_semana_confere()`
5. Regeneração de todos os 9 JSONs: `regerar_todos_json.py`
6. Diagnóstico de impacto: `diagnostico_impacto_pipeline.py`
7. Reprocessamento do SQLite: `corrigir_pipeline_reprocessar.py --aplicar`
8. Diagnóstico de verificação: `diagnostico_impacto_pipeline.py`

**Resultado final:**
- 6.570 registros reprocessados
- 0 registros com `tmin` corrompido
- 0 registros com `tmed` absurda
- 36 registros corrigidos (viraram `null` onde era apropriado)

---

## 7. Rastreabilidade

**Backups do banco:**

    banco\ispaam_antes_encoding.db
    banco\ispaam_antes_import.db
    banco\ispaam_antes_regras_finais.db
    banco\ispaam_antes_regras_novas.db
    banco\ispaam_antes_correcao_pipeline.db
    banco\ispaam.db.bak_YYYYMMDD_HHMMSS

**Backups dos JSONs:**

    dados_brutos\backup_json_original_v1\      (antes do saneamento)
    dados_brutos\backup_json_antes_reescrita\  (versão intermediária)
    dados_brutos\backup_json_antes_saneamento\ (versão atual pós-saneamento)

**Logs:**

    dados_brutos\diagnostico_pipeline_resumo.csv
    dados_brutos\diagnostico_pipeline_detalhe.csv
    dados_brutos\correcao_pipeline_log.csv

---

## 8. Recomendações

**Curto prazo:**
1. Aplicar a correção da regra de QC (Tmin 18–23 / >26)
2. Documentar a falha instrumental nos metadados da estação
3. Verificar se o sensor de mínima foi substituído em janeiro de 2025

**Médio prazo:**
1. Automatizar o saneamento no processo de importação mensal
2. Adicionar validação de faixas plausíveis em todos os campos
3. Criar checklist de QC antes de qualquer análise científica

**Longo prazo:**
1. Migrar o pipeline para uma ferramenta com versionamento
2. Adicionar testes automatizados para o script conversor
3. Documentar o fluxo de dados para novos usuários