# RAG V1.03-D-C — Isolated embedded runtime repair rehearsal

Date: 2026-10-20
State: PREPARATION VERIFIED, INSTALLED RUNTIME NOT MODIFIED
Branch: rag-017-optimized-inference-after-candidate
Production permission: NOT GRANTED by this audit

## Initial read-only finding

CodeBridge 2.0.11-prealpha READY.
Installed embedded Python (Python 3.13) exists and pip is operational.
Installed python313._pth does not expose ..\\.. (installation root).
Installed embedded Python lacks qdrant_client and cannot import rag.
Existing bootstrap source already has both requirements and correct root path.
Production public index remains legacy READY, 210 documents / 8761 chunks.
Model Jina Text and Code are installed; no auto worker or publisher enabled.

## Rehearsal performed (all in isolated TEMP staging)

- Embedded Python pip install --target into a fresh TEMP directory for qdrant-client==1.19.1.
- Dependencies were NEVER installed into Programs/CodeBridge.
- Tested embedded Python with temporary sys.path injection for staged dependencies and repository root.
- Imports passed for qdrant_client==1.19.1 and offline worker.
- Real embedded Python executed isolated synthetic Git / Jina Code staging E2E: 1 test PASS.
- No public index activation, pointer modification or persistent worker startup.
- Staged dependency directory: CodeBridge-RAG-DC-Dependency-Staging under OS TEMP (laboratory artifact, not installation).
- System Python prior real Jina independent-process E2E remains valid.

## Productized validations

- installer/runtime_readiness.py: read-only audit, returns structured missing-module evidence.
- installer/runtime_staging_verify.py: verify temporarily staged dependencies without changing active runtime.
- Installer NSIS payload includes the two diagnostics.
- bootstrap.ps1 -AuditOnly performs diagnostic without installation or directory creation.
- Installer regression suites passed: 13 then 15 tests; incremental regression: 284 PASS.
- Git staged diff and SHA verified at each commit.

## Key outcome and blocker

Runtime compatibility has been DEMONSTRATED in an isolated rehearsal.
CodeBridge installed runtime is STILL NOT REMEDIATED. A future controlled
application update must deploy validated root import path and missing
dependencies and rerun embedded runtime E2E without live MCP disruption.
This requires operator-approved maintenance when appropriate.
Do not use current staging proof as installed readiness or GO-LIVE.

## Protection

- Leave active RAG files, SQLite, Qdrant, generation pointer and Jina models unchanged.
- Preserve two preexisting Git dirty items without stage/cleanup.
- No scheduler, backup, process kill, destructive operation or production cutover.
- Do not automatically replace embedded runtime just because AuditOnly reports BLOCKED.
