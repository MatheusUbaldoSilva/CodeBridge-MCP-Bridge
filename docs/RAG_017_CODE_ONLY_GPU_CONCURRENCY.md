# RAG-017 — Diagnóstico Code-only de concorrência e GPU

Branch experimental `rag-017-optimized-inference-after-candidate`. A build dual candidata continua preservada na tag `rag-017-candidate-cross-route-quality-20261009`.

Teste real de duas consultas simultâneas (ThreadPoolExecutor com 2 workers) após uma consulta de carga inicial: inicialização 9020ms; consultas concorrentes 85,47ms e 187,21ms, ambas com resultados. A amostra é pequena, não certifica p95 sob carga e utiliza o mesmo cliente Qdrant experimentalmente compartilhado.

Medição de GPU Code-only: 88 MiB antes, 3204 MiB com o Jina Code residente, 3204 MiB após três embeddings e 88 MiB após encerramento. Capacidade informada 6144 MiB. São snapshots de GPU, não máximo contínuo, nem pico de RAM total com subprocessos. Os processos foram descarregados corretamente.

Qualidade experimental nas 100 perguntas conhecidas: Recall@5 0.88, Recall@10 0.92, MRR 0.692944. Falta holdout independente com ground truth previamente rotulado.

**Produção BLOCKED:** concorrência mais ampla, testes de falha/recuperação, p95 representativo, medição de pico RAM/VRAM, verificação dos filtros no serviço completo e validação independente ainda pendentes. Nenhum deploy ou modificação na build de referência.
