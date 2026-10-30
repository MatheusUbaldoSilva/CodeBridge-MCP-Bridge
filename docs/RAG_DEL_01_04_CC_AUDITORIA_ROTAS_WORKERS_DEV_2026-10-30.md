# RAG-DEL-01.04-CC — Auditoria de rotas de workers e congelamento (DEV)

Data: 2026-10-30. Escopo: inspecao do codigo-fonte; sem instalar, iniciar ou interromper workers reais.

## Rotas que compartilham reserva central

| Entrada observada | Contrato atual | Resultado do freeze Y/Z |
|---|---|---|
| auto_index_worker.execute_auto_index_batch | reserve_index_supervisor antes do writer; heartbeat periodico via renew_index_supervisor; protecao semantic nos vetores | Nova reserva negada sob BEGIN IMMEDIATE enquanto FROZEN. Worker JA reservado pode manter a renovacao e deve ser drenado separadamente. |
| auto_index_incremental_supervised | reserve_index_supervisor e release_index_supervisor | Nova reserva negada. Reavaliar chamadas subsequentes que dependem de token ja obtido. |
| auto_index_incremental_fenced | renew_index_supervisor + production_generation_lock semantic exclusivo | Nao faz nova reserva central neste modulo. Freeze nao invalida lease antigo; quiescencia deve inspecionar singleton, jobs e lock semantic. |
| auto_index_supervisor._change_lease | renova ou libera lease com ownership/generation | Deliberadamente NAO bloqueado pelo freeze para nao impedir drenagem e release. |

## Outras rotas detectadas

- auto_index_checkpoint: recuperacao de lease expirado altera auto_worker_lease diretamente e reencaminha um job para QUEUED, mediante validacao. O freeze nao bloqueia essa escrita: o guard de quiescencia recusa job nao terminal e a reserva nova continua bloqueada.
- auto_index_controls: comandos de pausa/cancelamento podem limpar token e aumentar a generation do lease. Nao equivalem a uma prova de shutdown de worker/processo.
- incremental_supervisor_fence usa um arquivo/SQLite isolado supervisor_fence.sqlite3, nao o mesmo singleton auto_worker_lease. Este modulo emite generation para experimentos; a compatibilidade com a politica de freeze operacional NAO foi certificada.
- production_generation_read e production_generation_transition usam lock generation. isolated_project_search, auto_index_worker e auto_index_incremental_fenced usam semantic. Falta auditar wrappers GUI/MCP, leitores antigos e todas as entradas efetivas da instalacao.

## Correcao importante de ordenacao

A fase BB corrigiu a ordem do executor em laboratorio para:

**generation exclusivo -> semantic exclusivo -> queue BEGIN IMMEDIATE**

O worker pode manter semantic enquanto o thread heartbeat solicita SQLite BEGIN IMMEDIATE para renovar o lease. A ordem anterior (queue -> generation -> semantic) poderia prender o heartbeat aguardando o queue enquanto o executor aguardasse semantic. O teste dedicado comprova que o queue permanece disponivel durante a espera por semantic.

Esta correcao elimina o ciclo conhecido no executor testado, NAO prova inexistencia de deadlocks em toda a aplicacao.

## Nao concluido

1. Falta prova exaustiva das rotas GUI, MCP, workers legados e leitores que possam ignorar o gate central.
2. Falta um procedimento AUTORIZADO de drenagem/reconciliacao de jobs READY_FOR_REVIEW, QUEUED, RUNNING e leases expiradas; nunca cancelar ou limpar automaticamente.
3. Nao existe aprovacao para aplicar freeze no banco real. A API de escrita do marcador permanece restrita a TemporaryDirectory.
4. Nao foi feita troca de geracao operacional, exclusao de documentos, escrita em Qdrant real ou modificacao da Stable.
5. Proximo passo recomendado: construir uma matriz automatizada de cobertura de entradas e testes de lifecycle que integrem freeze, heartbeat, recovery e interacao com leitor em ambiente de integracao totalmente isolado. Depois, obter aprovacao explicita para qualquer piloto operacional.

## Evidencias de teste nesta sessao

RAG-DEL: 270 executados, 268 PASS, 2 SKIP. RAG-AUTO exceto caso MCP: 241 executados, 236 PASS, 5 SKIP. Zero falhas nas suites executadas. MCP nao validado por falta do pacote Python no runtime DEV.
## DD — Leitura direta do ponteiro publico

Em auto_index_worker._public_generation, o arquivo active-generation.json e lido diretamente por Path.read_text, inclusive durante o ciclo do worker, sem o context manager production_generation_read. Essa observacao nao prova uma falha ativa porque o ponteiro nao foi trocado nesta sessao; e uma lacuna de cooperacao a auditar antes de qualquer cutover operacional. production_generation_read, por sua vez, usa lock generation compartilhado e recusa journal de transicao pendente. Exigir cobertura de TODOS os caminhos que leem o ponteiro, incluindo GUI/MCP e workers, antes de ativar o executor real. A fase DD foi somente uma auditoria estatica; nenhum arquivo em producao foi alterado.
