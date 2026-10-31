# RAG-DEL-01.04 DQ-E-D-3C-G-21 — Domain-separated stdio descriptor HMAC contract

Introduced a new scratch-only, versioned HMAC-SHA256 transcript (V2) that signs immutable session ID, fresh challenge, request hash, project namespace, generation, child PID, Win32 creation FILETIME and all three exact 64-hex stdio security-descriptor receipt hashes. Invalid keys, malformed digests, altered filetime/PID, wrong session or secret all fail closed. The preexisting V1 birth MAC remains available for earlier lab compatibility but cannot satisfy the V2 verifier.

Eleven unit tests PASS. This stage contains only a pure cryptographic contract and tests. It does NOT yet wire V2 to the scratch subprocess or production worker. Even when wired, equal SDDL hashes are not a unique kernel-object identity or an effective ACL authorization proof. Operational activation stays false; real queue/index, installed GUI/MCP, Stable and GitHub unchanged.
