# RAG-DEL-01.04 DQ-E-D-3C-G-8 — Domain-separated birth MAC (lab)

A versioned, domain-separated HMAC transcript now includes the exact Win32 creation FILETIME as well as session challenge, request hash, project, generation and child PID. The real scratch child signs this extended transcript; the parent independently reads creation FILETIME from its held Win32 process handle and verifies the extended HMAC. Legacy scratch HMAC remains for backward-compatible tests but cannot satisfy the birth-bound verifier.

Seven new tests PASS; 23 targeted G-4/G-5/G-8 tests PASS total. False birth, PID, challenge, session, malformed type and legacy-version MAC are rejected. Still laboratory only: protected handle inheritance and secure connection to the installed semantic worker remain unimplemented. Stable/operational data/queue/GitHub unchanged.
