# RAG-017 — Dependências nativas em runtime Python isolado (2026-10-10)

Criado ambiente virtual novo em `%TEMP%\CodeBridge-RAG017-NativeDeps-20261010` com Python Windows 3.13.15, sem alterar o runtime Python embutido do CodeBridge instalado. Instalados por pip somente wheels binários: `numpy==2.5.3`, `qdrant-client==1.19.1` e dependências, além de `author_mcp/requirements.txt` (`mcp==2.2.0`, pydantic, psutil e transitivas). As duas instalações encerraram com `PIP_EXIT=0` e `MCP_DEPS_EXIT=0`.

O verificador `benchmarks/rag017_isolated_embedded_probe.py` executado com esse venv sobre o payload NSIS isolado `%TEMP%\CodeBridge-RAG017-Isolated-Retest-20261010` reportou `rag=true`, `numpy=true`, `qdrant_client=true`, `mcp=true`, `pydantic=true`, `isolated_import_ok=true`, `deployment_ready=true`, código de saída zero. `pip check`: `No broken requirements found.` Listener MCP original em 127.0.0.1:8765 permaneceu PID 12776.

Limitações: `deployment_ready` significa apenas presença das dependências e capacidade de importação no **venv isolado**, não certifica Qdrant local com persistência, MCP end-to-end, empacotamento de wheels no Python embutido, segurança da atualização, rollback ou qualidade de busca independente. Instalação principal preservada; RAG-017-J e promoção a produção permanecem BLOCKED.
