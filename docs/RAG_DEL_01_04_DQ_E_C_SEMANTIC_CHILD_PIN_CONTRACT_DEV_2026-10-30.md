# RAG-DEL-01.04-DQ-E-C — Contrato de pin semantico e locks no subprocesso (DEV)

## Evidencias read-only

O codigo atual rag/runtime/isolated_project_search.py contem semantic_isolated_project(), que adquire production_generation_lock(exclusive=True,channel="semantic") internamente e inicia o processo rag.runtime.isolated_project_worker. A rota search_isolated_project() entrega semantic_isolated_project ao search_context como semantic_executor.

No subprocesso rag/runtime/isolated_project_worker.py, main() chama resolve_isolated_project(data["project_id"]), ou seja, resolve o catalogo novamente. Nao existe ainda um campo de handoff pinned_manifest_sha256 que prove que a geracao/manifesto consumido no worker e o mesmo retido pelo leitor pai durante toda a inferencia. Resolver e validar hash no worker, como existe em isolated_project_index.py, nao substitui a prova de uma sessao parent-child integral.

Envolver diretamente a rota semantica existente com outro lock semantic exterior pode tentar readquirir o mesmo lock. Se o pai mantiver mutex de catalogo enquanto aguarda um worker que passe a adquirir catalogo, surgira outra possibilidade de ciclo. Por isso a integracao operacional permanece BLOQUEADA.

## Guard de contrato adicionado

rag/runtime/knowledge_deletion_dqec_semantic_contract_dev.py faz exclusivamente AST read-only para registrar:
- parent_internal_semantic_lock;
- child_re_resolves_catalog;
- child_accepts_explicit_pinned_manifest;
- safe_to_activate e operational_use_allowed ficam SEMPRE False.

3 testes novos passam. Um teste de source sintetico melhorado continua sem autorizar uso real, pois atestacao carregada nao e demonstravel por AST.

## Direcao segura para proxima fase

Separar executor de inferencia que exija semantic ja detido de wrapper legado que adquire semantic sozinho, evitando reentrada. Vincular IPC do child a identidade assinada da geracao/manifesto definida no pai, comparar hashes antes/depois, e verificar se o worker depende de qualquer mutex ja detido pelo pai. Provar isso em scratch com subprocessos reais e shutdown sob falha, sem indexar dados reais. O contrato completo deve ainda respeitar generation(shared) -> semantic(exclusive) -> catalog e as garantias de heartbeat da fila.

## Resultado e limites

RAG-DEL: 353 executados, 349 PASS, 4 SKIP. RAG-AUTO sem MCP: 241 executados, 236 PASS, 5 SKIP. Total 594, 585 PASS, 9 SKIP, zero falhas.

A GUI Stable/candidato ainda nao tem public pinned helper, e o MCP conectado nao expoe o generation probe. Fila real tem READY_FOR_REVIEW pendente. Nenhum processo real, Stable, catalogo real ou GitHub foi modificado; nenhuma exclusao operacional autorizada.