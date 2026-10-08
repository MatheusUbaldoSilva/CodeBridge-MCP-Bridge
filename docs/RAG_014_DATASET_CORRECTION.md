# RAG-014 — Correção de integridade do dataset antes das métricas

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-014-benchmark`

## Motivo

Antes de executar RAG-014-C foi auditado se cada fonte de ground truth realmente pode entrar no índice segundo a política oficial de fontes

A auditoria encontrou quatro consultas do bucket `logs` cujo ground truth apontava somente para arquivos RAW negados pela política de indexação

Consultas afetadas

```text
rag014-081
rag014-082
rag014-083
rag014-088
```

Os paths eram

```text
phase4_restart.log
restart_app_phase5.log
.mcp_transition_err.log
.transition_mcp_err.log
```

Esses arquivos não são candidatos válidos do RAG

Usá-los como única fonte esperada faria quatro consultas serem impossíveis de recuperar mesmo com um retriever perfeito

## Correção

As quatro consultas foram mantidas no mesmo bucket `logs` e com os mesmos IDs

O conteúdo foi corrigido para avaliar a política real do CodeBridge

- por que RAW de restart e transition não entra diretamente no índice
- quais campos RAW são proibidos
- quais metadados estruturados de execução são permitidos
- como falhas viram structured_error sem copiar stdout/stderr bruto

Ground truth passou a apontar para fontes autorizadas

```text
rag/sources/exclusion_policy.py
docs/RAG_002_E_EXCLUSIONS.md
rag/sources/execution_inventory.py
docs/RAG_002_D_EXECUTION_SOURCES.md
```

## Invariante novo

Foi adicionado teste que exige

`cada consulta deve ter ao menos uma expected source elegível para indexação`

Elegibilidade usa as próprias políticas de produção

- `classify_denied_path`
- `is_document_source`
- `is_code_source`

Resultado após a correção

```text
UNRETRIEVABLE 0
[]
```

## Impacto

A distribuição continua exatamente

```text
25 code
25 docs
20 errors/audits
10 git
10 logs
10 pt-BR/code
total 100
```

Nenhum ID foi removido ou renumerado

A correção não altera o critério `ANY_EXPECTED_PATH_IN_TOP_K`

Ela apenas remove ground truth impossível de satisfazer sob a política real de segurança e ingestão

## Relação com RAG-014-C

RAG-014-C só pode começar a medir Recall e MRR depois que o ground truth for recuperável pelo corpus autorizado

Essa auditoria evita produzir uma métrica artificialmente pior por causa de fontes que o próprio RAG é obrigado a excluir
