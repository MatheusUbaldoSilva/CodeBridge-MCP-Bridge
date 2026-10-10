RAG-017 — Qdrant Local persistência isolada (2026-10-10)

Executado com Python 3.13.15 do venv temporário `%TEMP%\CodeBridge-RAG017-NativeDeps-20261010`, usando qdrant-client 1.19.1. Script `benchmarks/rag017_qdrant_isolated_persistence.py` operou exclusivamente em `%TEMP%\CodeBridge-RAG017-Qdrant-Probe-20261010` e rejeita armazenamento fora do prefixo experimental previsto.

Na primeira invocação, foi criada coleção com dimensão vetorial 4 e distância COSINE, inserido um registro ID 17 com payload marker rag017-isolated-only; contagem 1; processo encerrado com WRITE_EXIT=0. Em segunda invocação independente, novo cliente Qdrant Local reabriu diretório persistente e recuperou ID 17 e payload idêntico; contagem 1 e READ_EXIT=0. A prova é de persistência básica local após fechamento do cliente e fim do primeiro processo, não mede resiliência a falhas abruptas, índices reais RAG, concorrência, corrupção ou recuperação em produção.

O MCP principal continuou em porta 8765; nenhuma mudança no runtime instalado ou nos dados RAG reais. RAG-017-J permanece BLOCKED e holdout independente pendente.
