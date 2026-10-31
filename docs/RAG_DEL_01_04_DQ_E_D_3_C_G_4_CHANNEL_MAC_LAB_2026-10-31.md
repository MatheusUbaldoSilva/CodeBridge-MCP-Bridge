# RAG-DEL-01.04 DQ-E-D-3C-G-4 — Lab session MAC contract

Added a synthetic HMAC-SHA256 contract with an independent 256-bit secret per session. Canonical signed fields: protocol version, session ID, fresh challenge, request SHA256, project, generation, child PID. Verification uses constant-time compare; rejects changed request, session, challenge, namespace, generation and PID.

Eleven unit tests PASS. This is a mathematical MAC contract ONLY. No transport is implemented, and no evidence exists that the secret is exclusively and safely delivered to the intended child. It must not be passed via command line, environment variables or persistent files. A future phase must establish handle-based secure secret provisioning and real process linkage, and explicitly test replay across sessions under real Win32 execution.

No real worker change, model load, Qdrant access, deletion, Stable mutation or GitHub push. Activation remains false.
