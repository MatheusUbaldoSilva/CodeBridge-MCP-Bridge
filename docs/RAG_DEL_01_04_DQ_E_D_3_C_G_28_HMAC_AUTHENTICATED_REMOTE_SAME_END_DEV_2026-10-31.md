# RAG-DEL-01.04 DQ-E-D-3C-G-28 — HMAC-bound live Win32 same-end child proof (DEV)

The controlled G-26 child now receives a fresh 256-bit secret and session/challenge strictly over scratch stdin and signs its PID, Win32 creation FILETIME, and exact native std-handle values using the G-27 domain-separated HMAC-SHA256. Parent checks session challenge, PID/birth against the held spawned PROCESS HANDLE, verifies HMAC and ONLY THEN duplicates remote child std handles to compare same-end kernel-object identity. Child stays alive until parent explicitly sends ACK. No secret in argv/env/disk.

Four new G-28 adversarial tests PASS (valid session, altered MAC, changed native handle, multi-run) and updated G-26 shape test remains PASS (7 tests); total combined 11 PASS without ResourceWarning. Injected unauthenticated MAC fails before any remote handle comparison.

This authenticates a scratch subprocess under its parent-held process identity. It still does not attest Windows effective ACL/token rights, absence of unrelated inherited handles, installed CodeBridge GUI or production binary provenance. No operational deletion, queue/journal mutation, Stable or GitHub push.
