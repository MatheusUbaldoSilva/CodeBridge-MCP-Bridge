RAG-017 — Interrupção durante sequência de gravações Qdrant (2026-10-10)

Teste em venv temporário Python 3.13.15 e índice descartável `%TEMP%\CodeBridge-RAG017-MidWrite-20261010`. Script `benchmarks/rag017_qdrant_midwrite_probe.py` confirmou inicialmente registro ID=1 em coleção canário, `baseline_committed=true`, `count=1`. Em seguida iniciou loop de upserts individuais `wait=True` de IDs 2..100001, com progresso a cada 100 registros.

PID 12624 identificado via Win32_Process como processo do teste foi encerrado por `Stop-Process -Force` durante a sequência. Último progresso reportado: 3600; nova instância Python reabriu o banco e recuperou baseline com `baseline_intact=true` e 3620 registros sobreviventes; `CHECK_EXIT=0`. A instância MCP original permaneceu na porta 8765, PID 12776.

Limitações: término em meio ao loop, NÃO há garantia de que o kill coincidiu com operações de disco parcialmente gravadas; `wait=True` confirma operações anteriores. Não se certificam atomicidade por lote, última operação, fsync, corrupção física ou recuperação de produção. RAG-017-J segue BLOCKED.
