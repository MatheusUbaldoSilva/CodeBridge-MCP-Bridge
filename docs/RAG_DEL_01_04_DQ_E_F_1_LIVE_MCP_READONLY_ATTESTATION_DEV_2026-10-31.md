# RAG-DEL-01.04 DQ-E-F-1 — Live MCP read-only attestation (DEV)

The DEV probe client lists tools and calls codebridge_rag_generation_probe on the already running loopback MCP service. This is a read-only observation, not an installation change or permission to delete.

Evidence observed 2026-10-31: MCP generation v1_delta_1ae1d01ea84f4e, listening process PID 1184 on 127.0.0.1:8765, 27 exposed tools, required readers and locking checks passed. The attestation checks server-returned PID and explicitly fails closed for missing read-only metadata, malformed responses or mismatched PID. PID identity alone is not cryptographic authentication.

Tests: 10 unittest PASS for synthetic evidence; live tool listing and probe PASS. This stage does not attest GUI runtime, semantic child operation or live queue barrier. Authorization flags remain false and deletion is blocked. Stable, real queue, indexed data and Github unchanged.
