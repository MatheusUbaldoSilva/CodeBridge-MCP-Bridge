# RAG-017 — Extração isolada e rollback limitado (2026-10-10)

Build experimental `de21fcc`. O instalador NSIS não oferece isolamento suficiente na máquina principal: o fluxo atual grava chaves HKCU do CodeBridge, recria atalhos e executa `extension_setup.py --ensure-codebridge`, que pode iniciar a aplicação. Por segurança, **nenhum instalador foi executado**.

O arquivo `installer/dist/CodeBridge-Setup.exe` foi extraído pelo 7-Zip em `%TEMP%\CodeBridge-RAG017-Extract-20261010`, com exit code 0: 157 arquivos, incluindo 83 fontes Python em `rag/`. Presentes `rag/__init__.py`, `rag/contracts.py`, `rag/runtime/production_search.py`, `author_mcp/mcp_server.py` e `installer/bootstrap.ps1`. O hash do `mcp_server.py` extraído coincide com o código-fonte (`72CCDAFF8B7C53A5B1AA29A7D3BB4AD4DB9C6776B4F1FF7869040FC8D55A7D2D`).

Usando o Python de `author_mcp/.venv` e `PYTHONPATH` temporário para a pasta extraída, os imports de `rag.contracts`, `rag.runtime.production_search` e `rag.runtime.status` terminaram com exit 0. Isto não prova integração no Python embutido.

Um ensaio limitado de rollback foi realizado exclusivamente em `%TEMP%\CodeBridge-RAG017-RollbackDryRun-20261010`: cópia de `mcp_server.py`, substituição simulada por conteúdo inválido e restauração do backup. O SHA-256 final correspondeu ao original (`ROLLBACK_DRYRUN_PASS=True`). **Não é prova de rollback integral do NSIS** (registro, atalhos, processos, configurações, dependências e arquivos).

A instância original MCP permaneceu em `127.0.0.1:8765`, PID 12776, sem reinício. Próxima fase: construir instalação isolada sem efeitos de registro/atalhos ou usar VM descartável e comprovar rollback completo. Gate RAG-017-J: BLOCKED.
