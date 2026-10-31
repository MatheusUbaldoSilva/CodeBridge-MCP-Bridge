# RAG-DEL-01.04 DQ-E-D-3C-G-27 — Domain-separated same-end native handle HMAC contract (DEV)

Introduced an isolated, pure HMAC-SHA256 transcript signing a 256-bit session key, session ID, fresh challenge, strict scratch project/generation, child PID, native process creation FILETIME and the three Win32 std-handle numeric values. Canonical JSON and an explicit domain separator prevent confusion with G-21 descriptor MAC protocol. Verification uses constant-time compare_digest; malformed messages and any altered PID/birth/handle/challenge fail closed.

Eleven tests PASS: challenge/session replay, wrong key, changed handles, invalid project, malformed handle set, boolean PID and malformed signature.

Only the standalone cryptographic contract is implemented at G-27; it has not yet been attached to G-26 real subprocess. The real child wiring and adversarial integration are G-28. This is scratch-only with no production RAG activation or access to live models, indexes or queues.
