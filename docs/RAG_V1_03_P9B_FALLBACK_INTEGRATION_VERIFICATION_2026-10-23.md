# P9-B ? Jina Code staged CPU fallback verification (2026-10-23)

Status: synthetic integration PASS, real CPU E2E NOT EXECUTED, P9-B OPEN.

## Implemented in Git

- eb45aca: production_index._write_vectors uses existing TextModelFallbackManager
  with CodeModelLifecycle and cpu fallback config device=none, gpu_layers=0.
- 07e6f6c: isolated wiring and cleanup tests without starting GPU or llama.
- 99578dc: failed embedding closes lifecycle and Qdrant without vector upsert.
- 0927dea: real fallback manager with simulated GPU ModelLoadError chooses CPU.
- 4a6ffe6: GPU and CPU failures both block upsert and close Qdrant.

Five integration tests PASS with installed Python and Git root first on sys.path.
Existing eleven tests for TextModelFallbackManager PASS.
No public generation switch, NSIS, index mutation, or real GPU load by the tests.

## Background and remaining gates

Previous installed worker E2E returned SCHEDULED_RETRY / ModelLoadError.
llama-server log showed CUDA0 cudaMalloc out of memory requesting 1564.63 MiB.
Do NOT claim E2E success from deterministic synthetic tests.
RAG public status remains READY at generation v1_delta_1ae1d01ea84f4e
with 211 documents / 8774 chunks. Jina Code reported GPU LOADED at latest
status check; avoid competing real GPU worker while it is loaded.

Before production acceptance:
1. Test isolated CPU fallback E2E with available memory and no interference.
2. Confirm exact embedding shape/dimension and staged receipt.
3. Verify public index hash unchanged and no unexpected new generation.
4. Confirm shutdown supervisor and NSIS transactional rollback independently.
5. Verify public CBMCP/1 reconnect, durable queue, scheduler, and RAG after
   an operator-approved maintenance cutover.

No live cutover authorized by these test results.
