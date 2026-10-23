# P9-B / Installed Jina Code worker failure evidence

2026-10-23 ? P9-B OPEN / no NSIS real cutover

Isolated test: test_incremental_installed_worker_e2e.py
Execution ~21.4 seconds, 25 tests, one failure.
Expected STAGED_OFFLINE_VALIDATED, observed SCHEDULED_RETRY,
error_type=ModelLoadError and active_index_updated=False.

Log %LOCALAPPDATA%/CodeBridge/logs/rag/jina-code-embeddings-1.5b/llama-server.log
contains CUDA0 cudaMalloc out of memory while requesting 1564.63 MiB
(1640632832 bytes) for pinned Jina Code Q8_0.
At observation, nvidia-smi showed 3217 MiB / 6144 MiB used.

This is confirmed GPU capacity contention, NOT evidence of lost queue
data or successful indexing. Do not label the E2E PASS.
Do not force GPU model retries under the same pressure.
Next step is audit existing CPU fallback path for production_index.build_staged_index,
create deterministic unit tests first, then controlled CPU-only E2E when
resources are available. Retain fail-closed queue semantics and
never update the active index on model failure.
