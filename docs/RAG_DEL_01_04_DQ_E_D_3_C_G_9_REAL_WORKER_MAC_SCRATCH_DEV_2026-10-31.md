# RAG-DEL-01.04 DQ-E-D-3C-G-9 — MAC scratch mode in real worker entrypoint

The actual isolated_project_worker.py now accepts one additional explicit opt-in command-line mode: --pinned-mac-scratch. It exclusively calls the HMAC synthetic child handler. No project resolver, semantic model, SQLite, Qdrant or deletion operation is invoked in this mode. The existing default worker remains unchanged.

The lab parent supports only enumerated synthetic and real-worker scratch modes and launches a child using private anonymous stdin/stdout pipes and a direct base interpreter. Roundtrip validates challenge/request scoped birth-bound HMAC against child PID and Win32 creation FILETIME observed from the held subprocess handle.

Four new tests PASS; 16 selected regression tests PASS including existing pipe/MAC cases. This is not production transport authentication, does not audit pipe ACL, and does not provide authority to delete. Installed GUI/MCP processes, Stable, indexes, real queue and GitHub unchanged.
