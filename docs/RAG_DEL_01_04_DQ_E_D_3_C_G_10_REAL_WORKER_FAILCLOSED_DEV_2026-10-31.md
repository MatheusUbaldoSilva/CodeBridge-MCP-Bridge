# RAG-DEL-01.04 DQ-E-D-3C-G-10 — Real-worker scratch denial coverage

Seven new subprocess tests execute the real isolated_project_worker entrypoint with missing stdin, malformed JSON, unexpected CLI flags, unbounded line, extra fields and an unauthorized private project payload. All seven fail closed, as expected. No operational search or deletion is invoked, and the secret value is not leaked into stderr in the examined error case.

This patch adds only negative tests and documentation; the source worker remains as committed at G-9. This does not certify production-grade IPC. The real queue, Stable, models/indices, installed GUI and remote GitHub remain untouched.
