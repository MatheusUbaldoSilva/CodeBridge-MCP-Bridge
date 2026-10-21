# RAG V1.03 P3 - Offline candidate source and vector validation

Date: 2026-10-21
Branch: rag-017-optimized-inference-after-candidate
Scope: read-only, candidate stored in local TEMP. No installed public generation cutover.

## Verified with CodeBridge on Windows

Baseline: TEMP/codebridge-rag-p2-closed-baseline/legacy
- 210 documents; 8761 chunks and vectors; 210 manifest entries
- SQLite integrity and Qdrant vector identities checked

Candidate: TEMP/codebridge-rag-p2-closed-baseline/candidate-merged-211
- 211 documents; 8763 chunks and vectors; 211 manifest entries
- SQLite integrity and Qdrant vector identities checked
- One added path: rag/runtime/incremental_scheduler_gate.py
- Zero modified or removed previous paths
- Added source SHA256: 6d0e790e82ee9bea7f163cf0b5244accc794a87bf6032d97144f73ab21c3feed

Full offline assessment: P3_OFFLINE_VERIFIED_NOT_AUTHORIZED
Negative SHA test: BLOCKED / exit 2, intentional.

## Implementation commits for this continuation

- e65bc1b: closed generation review bridge
- 5e5ce49: exact counts guard
- a188341: offline SQLite count inspection
- 305d916: manifest/source comparison
- 6baf3d0: combined cross-store P3 report
- 18c6035: repeatable read-only CLI

## Remaining blockers

This proof is NOT operator authorization and not a certificate of an installed public candidate.
Legacy public MCP remains on 210/8761 and must stay unmodified.
The historical supervised trial allowlist intentionally rejects this different candidate scope.
Production pointer switch, real rollback, MCP reader restart attestation and generation-specific authorization are not completed.
Do not bypass the old gate or mark GO_LIVE_APPROVED.
Before a supervised cutover, repeat actual read-only public status and consistency checks and obtain distinct explicit approval.

## Public MCP acceptance probes after offline validation

- codebridge_rag_status still reports generation=legacy, 210 documents, 8761 chunks.
- MCP text search returned 3 results with effective_route=TEXT, no fallback, including vector and lexical retrieval evidence.
- MCP code search returned 3 results with effective_route=CODE and no fallback.
- Path-filtered search for rag/runtime/incremental_scheduler_gate.py returned zero results, confirming this candidate-only source is not yet in the public generation.
- Public SQLite SHA256 remained 5bf26a6dd4e26334899b043a608ac3c8e316b7712e24b6ca1c17b7f9342cb764.
- Public manifest SHA256 remained eeb40201617444898f9f327fe73b2c50cd73d079b682f6576ac5f60ebf84fd1c.
- These observations are read-only and do not override the explicit GO_LIVE_BLOCKED state.

## Next actionable phase

The P3 offline data and actual MCP legacy-path checks are evidenced.
A real supervised generation transition is still a distinct operation and needs a generation-specific operator approval and verified rollback/readers evidence.
Without that authorization, the correct next action is preserve both stores and wait for operator review, not to modify or restart the installed public MCP.