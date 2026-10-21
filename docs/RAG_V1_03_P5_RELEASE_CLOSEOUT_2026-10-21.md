# RAG V1.03 P5 — Publicação concluída e auditada

Data 2026-10-21
Ambiente CodeBridge 2.0 MCP oficial Windows
Branch rag-017-optimized-inference-after-candidate

## Execução confirmada

- Ensaio supervisionado anterior: LIVE_TRIAL_PASSED_AND_ROLLED_BACK com v1_delta_3ab9c095605b4a
- Geração nova para publicação: v1_delta_1ae1d01ea84f4e
- Publicação permanente: RELEASE_ACTIVE_PUBLIC_VERIFIED
- Índice público real CodeBridge MCP: generation=v1_delta_1ae1d01ea84f4e
- Documentos 211, chunks 8774, vetores 8774
- codebridge_search_context filtrado em rag/runtime/incremental_scheduler_gate.py retornou 2 chunks CODE; verificação SHA_MATCH
- codebridge_get_context recuperou chunk da fonte nova com count=1
- Estado do índice READY
- Cross-store OBSERVED_CONSISTENT
- Ponteiro ativo com schema_version=1 e geração nova
- Nenhum journal de transição pendente
- Código de saída da rotina de publicação 0

## Recuperação preservada

- Índice SQLite legado hash 5bf26a6dd4e26334899b043a608ac3c8e316b7712e24b6ca1c17b7f9342cb764
- Manifesto legado hash eeb40201617444898f9f327fe73b2c50cd73d079b682f6576ac5f60ebf84fd1c
- Rollback journaled disponível no módulo rag/runtime/production_generation_transition.py
- Cópias imutáveis da baseline e candidata mantidas
- O ensaio antigo, de 8778 chunks, permanece separado e não foi reutilizado

## Entregas versionadas

- c7a07da ensaio supervisionado da candidata correta
- e720557 correção do fingerprint SHA
- ca0c08b recibo do ensaio de ativação/rollback
- 163b999 liberação específica com rollback em falhas
- 240f936 recibo de publicação

## Escopo de conclusão

Esta fase de transição pública e teste do novo índice está concluída.
A V1 inteira não deve ser marcada concluída por inferência desta etapa.
Automação de reindexação, scheduler e demais marcos futuros devem ser tratados separadamente e auditados antes de ativação.
Dois arquivos Git alterados desde antes da P5 foram preservados e não fazem parte destes commits.
