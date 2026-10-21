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
