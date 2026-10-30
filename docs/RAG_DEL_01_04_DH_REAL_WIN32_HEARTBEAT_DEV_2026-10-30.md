# RAG-DEL-01.04-DH — Processo semântico real e heartbeat SQLite (DEV)

## Motivação

O worker que segura LockFileEx exclusivo no canal semantic ainda precisa renovar seu lease pelo SQLite. A transição de exclusão precisa adquirir generation e semantic antes de BEGIN IMMEDIATE na fila. Se a fila ficasse retida enquanto se espera semantic, um heartbeat poderia bloquear (ciclo de espera).

## Testes realizados

O teste test_semantic_conflict_fails_without_blocking_heartbeat inicia um processo Windows real que mantém LockFileEx semantic em um root CodeBridge/rag sintético. Uma thread no processo atualiza uma tabela heartbeat por BEGIN IMMEDIATE em uma fila SQLite temporária. O processo que tenta laboratory_writer_fence falha em adquirir semantic sem deter a fila; o contador do heartbeat continua aumentando. Ambos os locks podem ser reutilizados após liberação.

O teste test_worker_crash_releases_win32_but_stale_lease_blocks_cutover mata abruptamente o processo com semantic reservado e confirma a liberação do lock pelo Windows. O freeze temporário e a lease SQLite expirada persistem; o gate da transição permanece bloqueado exigindo reconciliação. Não há limpeza automática de lease e nem ativação.

Ambos os testes usam apenas diretórios temporários, locks temporários, SQLite sintetico e subprocessos criados pelo teste. Nenhum worker, índice, projeto ou ponteiro real foi afetado.

## Limites

Esses testes não exercitam carregamento real do modelo, chamada MCP/UI, instalação Stable ou compatibilidade de todas as rotas. Uma lease expirada não indica por si só que o processo original terminou, e não autoriza substituição da geração. Qualquer recuperação real exige provas adicionais e autorização operacional.