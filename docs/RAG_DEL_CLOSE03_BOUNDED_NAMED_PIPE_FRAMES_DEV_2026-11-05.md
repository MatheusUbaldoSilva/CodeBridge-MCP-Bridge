# CLOSE-03 — Bounded Named Pipe frame reads (DEV)

Date: 2026-11-05 | Branch: dev-local

## Change

The generic Named Pipe framing API now accepts an optional per-receiver max_bytes on read_frame and NamedPipeConnection.receive. The 4 MiB transport default remains unchanged for existing callers. A supplied limit is validated before I/O, and the frame length is rejected immediately after reading the 4-byte header, before allocating/reading the body.

The DEV-only admission precheck now receives request frames with an 8 KiB limit and the close handshake with a 256-byte limit. Its former post-receive length check remains as defense in depth.

## Tests

- New bounded-frame unit tests: 4 PASS.
- Admission Named Pipe suite: 9 PASS.
- Combined IPC/pipe-related modules: 71 PASS, 0 skips/failures/errors.
- Full RAG-DEL suite: 840 run, 833 PASS, 7 SKIP, 0 FAIL.

## Boundaries

No production GUI wiring, Stable restart, queue/canary/catalog/generation mutation, or GitHub push. The newworldpvp canary remains KEEP and active. The generic default maximum remains 4 MiB for backward compatibility.

