# RAG-DEL-01.04-DE — leitura cooperativa do ponteiro pelos workers (DEV)

## Mudança

rag/runtime/auto_index_worker.py::_public_generation usava Path.read_text diretamente no active-generation.json, fora do lock generation e sem rejeitar journal de transição pendente.

Agora a função segura production_generation_lock(exclusive=False, channel="generation") durante a leitura. Resolve a raiz RAG pelo resolvedor do CodeBridge, recusa ausência/symlink do ponteiro, journal pendente e nomes de geração inválidos. Lock exclusivo ocupado por outro processo resulta em recusa fail-closed (ProductionGenerationBusy); nunca ignora a colisão.

auto_index_incremental_supervised importa esta mesma função, portanto também passa pelo guard ao obter/validar a geração. O guard é curto (apenas leitura do pointer), não prende a geração durante todo o trabalho de embeddings e NAO garante sozinho integridade completa do job.

## Ordem e condições de segurança

A ordem auditada do executor de exclusão LAB é generation -> semantic -> queue. Um worker já no lock semantic pode tentar o lock generation compartilhado. Se o executor estiver com generation exclusivo, o LockFileEx do Windows é não bloqueante e o worker deve falhar em vez de aguardar indefinidamente. Confirmar em futuro teste de ciclo de worker real, incluindo heartbeat e rollback.

## Evidência

Seis testes em TemporaryDirectory/CodeBridge/rag exercitam o LockFileEx real e ponteiro temporário, inclusive colisão de outro processo, ausência, journal, nome inválido e leitura sem mutação. Não houve acesso ao ponteiro real nos testes.

Regressão depois da mudança: 276 RAG-DEL (274 PASS, 2 SKIP) e 241 RAG-AUTO sem MCP (236 PASS, 5 SKIP), sem falhas.

## Pendências

- incremental_scheduler_public_pointer.py e outros caminhos de inspeção ainda leem ponteiro diretamente. A análise individual deve distinguir caminhos de migração controlada, observação read-only e leitores de produção.
- Falta comprovar que GUI/MCP e workers legados respeitam o lock e o journal em todas as operações reais.
- Nenhum cutover operacional, freeze na fila real, exclusão privada, push GitHub ou alteração da Stable foi autorizado.