# RAG-DEL-01.04 DQ-E-D-3C-G-5 — Anonymous pipe scratch MAC

Laboratory-only process roundtrip: parent creates 256-bit secret and per-session challenge, launches a synthetic child (no shell) using standard anonymous stdin/stdout pipes and close_fds=True, and passes the secret inside stdin framing rather than through argv, env, URL or disk. Child returns PID claim plus HMAC; parent verifies the exact scoped request and reaps the child on timeout/failure. Scratch namespace is strictly enforced.

Five unit tests PASS, including a real Python child handshake on Windows. No real RAG model, project, queue, Qdrant or deletion path is callable from the child.

SECURITY LIMIT: this only demonstrates possession of pipe-delivered secret. The returned child PID is a CLAIM and does not prove OS identity. Windows venv redirectors can change PID lineage. A future stage must bind the native process object and protected inherited handle/ACL to the secret transport. Neither installed MCP/GUI nor Stable was changed. No operational approval is possible.
