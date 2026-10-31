# RAG-DEL-01.04-DQ-E-D-2 — Separar aquisicao de lock e dispatch semantico (DEV)

## Codigo alterado
- rag/runtime/isolated_project_search.py: a funcao semantic_isolated_project continua a resolver o indice e adquirir semantic exclusive de modo legado, com retry por 100 segundos no estado ocupado.
- O subprocess.run e a conversao dos SearchResult foram extraidos para funcao interna _invoke_isolated_semantic_subprocess_unlocked(index,payload). Ela NAO adquire lock. Seu unico caller operacional continua sendo o wrapper legado.
- Nenhuma mudanca em isolated_project_worker.py e nenhuma passagem de envelope pinado foi conectada ao worker real. A chamada interna sem lock nao deve ser invocada por outro caminho operacional antes da atestacao do IPC.
- rag/runtime/knowledge_deletion_semantic_dispatch_lab.py: despachante de laboratorio somente, requer private_read_session_lab semantica JA ativa, gera o envelope TEMP DQ-E-D-1 e chama apenas callback sintetico injetado, SEM adquirir novamente lock semantic.

## Provas
10 testes novos PASS. A rota legada adquire semantic uma vez, retorna SearchResult equivalente, retry busy nao chama child ate deter lock, subprocess timeout libera a trava, erro de worker continua propagado, indice ausente recusa. O dispatcher lab valida projeto, aprovacoes, sessao e fecha corretamente em erro, nao readquire semantic, podendo invocar o worker de laboratorio DQ-E-D-1 sem iniciar modelos.

RAG-DEL: 373 testes, 369 PASS + 4 SKIP, zero falhas.
RAG-AUTO sem MCP: 241 testes, 236 PASS + 5 SKIP, zero falhas.
Total: 614 testes, 605 PASS + 9 SKIP, zero falhas.

## Gates nao concluidos
Nao afirmar que ha lock semantico gerenciado pelo parent no worker real; filho atual ainda re-resolve catalogo e nao recebe pin. A DQ-E-D-3 deve implementar e validar handoff do envelope real sob protocolo/lock ordenados, com fallback do legado e testes de subprocessos, antes de integracao operacional.
A GUI Stable e candidato selecionado tambem ainda nao incluem o helper publico pinado; MCP conectado nao expoe generation_probe. Fila real READY_FOR_REVIEW ainda bloqueia ativacao. Nenhum indice real, Stable, fila, instalacao ou GitHub foi alterado.