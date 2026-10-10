# RAG-017 — MCP isolado em porta alternativa (2026-10-10)

Foi iniciado um processo temporário a partir do staging `%TEMP%\CodeBridge-RAG017-Stage-20261010`, utilizando o virtualenv `author_mcp/.venv`, e servidor HTTP MCP local em `127.0.0.1:18765`, sem usar a porta `8765` do MCP instalado.

Um cliente MCP de teste completou handshake `initialize` e `list_tools`: **13 ferramentas**, incluindo todas as quatro ferramentas RAG esperadas: `codebridge_rag_status`, `codebridge_rag_index`, `codebridge_search_context` e `codebridge_get_context`. A chamada de leitura `codebridge_rag_status` retornou sem erro do protocolo (`RAG_STATUS_OK True`). O primeiro verificador falhou por referenciar `CallToolResult.isError` em vez de `is_error`; após ajuste o teste passou.

O processo temporário PID 13084 foi encerrado; posteriormente só a porta 8765 estava em escuta, com PID 12776 do MCP original. A instalação não foi alterada nem reiniciada. O script de consulta em `benchmarks/probe_rag017_staged_mcp.py` está coberto por `.gitignore`, portanto este relatório registra a prova sem adicioná-lo à versão.

**Limitações:** teste realizado em venv e não no Python embutido pelo NSIS; as 13 ferramentas foram anunciadas, mas não foi validado o funcionamento de busca e indexação em ambiente empacotado, instalação ou rollback. RAG-017-J e atualização instalada permanecem BLOCKED; build dual preservada.
