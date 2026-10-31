# RAG-DEL-01.04 DQ-E-D-3C-G-13 — Reusable DEV scratch soak

The manual benchmark repeats the isolated_project_worker --pinned-mac-scratch proof on real Win32 subprocesses without accessing models, SQLite, Qdrant or real deletion. Each run checks HMAC, PID, Win32 birth and non-authorization. Iteration count is bounded to 1..500. No process PID, secret or project path is reported.

Observed 2026-10-31: 80 consecutive real-worker scratch sessions passed in 16.085 seconds, with 77 distinct numeric PIDs (normal OS PID reuse may occur). The queue stayed blocked and deletion_authorized=false. Three unit tests PASS, including a two-run smoke.

No Stable, index or GitHub changes.
