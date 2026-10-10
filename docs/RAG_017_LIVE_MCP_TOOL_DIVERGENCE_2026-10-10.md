# RAG-017 — Divergência observada no MCP em execução (2026-10-10)

Diagnóstico somente leitura em MatheusPC. A conexão com o servidor MCP local `http://127.0.0.1:8765/mcp` foi estabelecida usando o cliente oficial do ambiente `author_mcp/.venv`. A negociação do protocolo foi bem-sucedida e `list_tools()` **não anunciou** `codebridge_rag_status` (`RAG_TOOL_AVAILABLE False`). O arquivo versionado `author_mcp/mcp_server.py` define esse instrumento, portanto existe divergência entre a interface anunciada pelo servidor ativo e o código-fonte atualmente auditado.

A consulta MCP autoral separada `codebridge_status` retornou READY, API online, versão `2.0.11-prealpha`, PowerShell/CMD online e SSH offline. Essa resposta não informa o registro dos executores RAG.

O primeiro teste com Python global falhou por falta do pacote `mcp`; ao usar `author_mcp/.venv/Scripts/python.exe`, a listagem do servidor ativo funcionou. Nada foi reiniciado ou configurado; nenhum modelo foi carregado.

**Não é possível concluir apenas com isso** se o serviço está usando build diferente, código anterior, filtros de publicação ou configuração distinta. Próximo passo: identificar a origem do processo MCP vivo e a lista efetiva de ferramentas antes de implementar instrumento de introspecção. A build dual e o gate BLOCKED permanecem preservados.
