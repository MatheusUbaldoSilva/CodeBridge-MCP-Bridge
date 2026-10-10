# RAG-017 — Ensaio de empacotamento isolado (2026-10-10)

Criado `benchmarks/stage_rag017_install_package.py`: copia o pacote RAG e arquivos MCP para diretório de staging novo, recusando sobrescrita. O teste executado em `%TEMP%\CodeBridge-RAG017-Stage-20261010` preparou **83 arquivos Python do pacote RAG**. Não escreve na instalação `%LOCALAPPDATA%\Programs\CodeBridge` e não ativa a rota Code-only.

Com o Python do virtualenv `author_mcp/.venv` e a raiz do staging incluída temporariamente em `sys.path`, os imports `rag.contracts` e `rag.runtime.production_search` passaram (`STAGED_IMPORT_OK`). Dois testes unitários cobrem criação, recusa de sobrescrita e ausência do RAG original.

**Não é um instalador pronto:** a árvore experimental copiada não equivale ao payload final NSIS; não foram validados todos os imports, dependências Python nativas do runtime embutido, inicialização completa MCP em porta isolada nem rollback. O script de staging não substitui a versão de produção e o NSIS ainda não inclui RAG; o gate estrutural permanece **BLOCKED**. Para liberar atualização, revisar dependências e paths no `bootstrap.ps1`, ampliar NSIS com empacotamento seletivo do RAG, testar em ambiente limpo e construir rollback verificável. Build dual tagueada preservada; holdout independente pendente.
