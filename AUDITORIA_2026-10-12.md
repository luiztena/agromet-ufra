# Registro de auditoria do pipeline UFRA-BEL

**Data:** 12 de outubro de 2026
**Duração:** 3 dias (10–12/10/2026)

---

## Linha do tempo

### 10/10/2026 — Diagnóstico inicial

- Rodado `diagnostico_tmin_sensibilidade.py`
- Descoberto viés de Tmin de −1,09 °C em 2018–2022
- Rodado `diagnostico_tmin_sazonalidade.py`
- Descoberta sazonalidade significativa (p < 10⁻¹²)

### 11/10/2026 — Investigação da quebra de 2023

- Rodada query SQL para cobertura mensal de Tmin
- Confirmada queda de cobertura de 80% para 25% entre jul/2023 e jan/2025
- Solicitado JSON de 2023 ao repositório
- Confirmada ausência de Tmin nos JSONs a partir de 23/07/2023

### 12/10/2026 — Correção do pipeline

**Manhã:**
- Escrito `diagnostico_impacto_pipeline.py`
- Rodado diagnóstico inicial: 36 registros com tmed absurda
- Escrito `regerar_todos_json.py` para automação
- Detectada diferença de encoding (cp1252 vs utf-8)

**Tarde:**
- Identificado bug em `_dia_semana_confere` (variável `s` indefinida)
- Adicionado `sanear_registro()` ao `planilha_para_json.py`
- Regenerados todos os 9 JSONs com sucesso
- Escrito `corrigir_pipeline_reprocessar.py`
- Backup do banco: `ispaam_antes_correcao_pipeline.db`
- Aplicada correção: `--aplicar`
- Rodado diagnóstico de verificação: **0 inconsistências**

---

## Artefatos gerados

**Scripts:**
- `scripts/_debug/diagnostico_impacto_pipeline.py`
- `scripts/_debug/corrigir_pipeline_reprocessar.py`
- `scripts/_debug/diagnostico_tmin_sensibilidade.py`
- `scripts/_debug/diagnostico_tmin_sazonalidade.py`
- `scripts/_debug/figura_diagnostico_tmin.py`
- `scripts/_debug/validacao_tmax_sensibilidade.py`
- `scripts/regerar_todos_json.py`
- `scripts/planilha_para_json.py` (modificado)

**Dados:**
- `dados_brutos/dados_YYYY.json` (9 arquivos regenerados)
- `dados_brutos/diagnostico_pipeline_resumo.csv`
- `dados_brutos/diagnostico_pipeline_detalhe.csv`
- `dados_brutos/correcao_pipeline_log.csv`

**Backups:**
- `banco/ispaam_antes_correcao_pipeline.db`
- `dados_brutos/backup_json_antes_saneamento/` (9 arquivos)

---

## Pendências conhecidas

1. Regra de QC de Tmin ainda mal parametrizada (23–26 °C marcado como atípico)
2. `DeprecationWarning` no `datetime.strptime(s, "%d/%m")` em dois scripts
3. 1 registro de 2020 rejeitado por dia da semana inconsistente (não investigado)

---

## Contatos

- Responsável pela auditoria: Luiz
- Data de revisão recomendada: abril de 2027