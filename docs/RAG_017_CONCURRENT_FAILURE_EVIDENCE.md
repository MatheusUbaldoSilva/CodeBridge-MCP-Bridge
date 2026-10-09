# RAG-017 — Falhas repetidas e recuperação concorrente

Branch experimental, sem alterar a tag candidata dual.

**Três encerramentos consecutivos do subprocesso Jina Code** foram detectados, o pool descartou a instância e uma consulta posterior voltou a gerar embeddings de 1536 dimensões. PIDs: 9204→4136→10876→3264. Teste executado em processo isolado; relatório `benchmarks/rag017_repeated_process_recovery.json`.

**Três requisições concorrentes após uma falha**: primeira falhou com `CodeEmbeddingStateError` (comportamento fail-closed esperado), segunda e terceira recuperaram com ~3575 ms e ~3629 ms, consulta posterior bem-sucedida. PID anterior 1428, novo PID 10584; relatório `benchmarks/rag017_concurrent_recovery.json`.

A recuperação é comprovada nos cenários controlados, mas a primeira requisição não foi atendida automaticamente; não alegar recuperação transparente. Ainda faltam p95 estatístico em carga, pico RAM/VRAM e holdout cego independente. Produção permanece **BLOCKED** e os thresholds não mudaram.
