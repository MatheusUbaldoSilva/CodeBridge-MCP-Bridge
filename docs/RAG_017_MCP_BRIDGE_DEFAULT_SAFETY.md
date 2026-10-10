# RAG-017 — Auditoria de segurança da integração MCP

Foi auditado o módulo `author_mcp/rag_bridge.py` e o adaptador `rag/runtime/production_search.py`. O fluxo MCP usa um executor semântico opcional, registrado somente por chamada explícita a `configure_production_rag_executors(semantic_search=True)`. Ambos os parâmetros `experimental_cross_route` e `experimental_resident_models` possuem padrão `False`. Registrar apenas o executor de indexação não habilita a busca semântica.

Os quatro testes novos em `tests/test_rag_017_installed_bridge_safety.py` verificam defaults desativados, busca MCP sem registro automático, registro explícito sem modificar os defaults e isolamento entre registro de índice e busca. Regressão: **802 testes RAG aprovados**.

Limitação: os testes são do código de integração e não inspecionam o estado de runtime da instalação empacotada, serviços do Windows, opções efetivas de deploy ou todo o ciclo de vida em execução. Não foi habilitado o recurso experimental. A tag dual original permanece protegida. Holdout independente e gate de produção continuam **BLOCKED**.
