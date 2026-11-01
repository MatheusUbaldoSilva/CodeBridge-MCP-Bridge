# RAG-DEL CLOSE-03 — Scratch kernel peer PID and birth validation

Date: 2026-11-01. Branch: dev-local. **Development-only evidence**.

## Implemented
- `rag/runtime/knowledge_deletion_scratch_pipe_peer_identity_dev.py`:
  obtains client PID and session from the actual scratch server pipe handle via
  native Windows GetNamedPipeClientProcessId/GetNamedPipeClientSessionId; opens
  kernel process handle and observes creation timestamp and token SID without
  modifying privileges or impersonating anyone. Compares expected PID/birth
  against OS evidence. Never authorizes deletion.
- `tests/test_rag_del_close_03_scratch_kernel_peer_identity_dev.py`:
  truly separate child process calls the existing source NamedPipeClient on
  unique scratch channel; detects and rejects spoofed claimed PID and
  mismatched process birth; validates normal kernel observation and bad input.

## Discovery
The Python virtual-environment launcher `Popen.pid` is not necessarily the
actual process PID opening the pipe. The kernel PID correctly tracks the child
which owns the connection, preventing a fragile parent-PID assertion.
Caller-provided PID in message payload is compared against kernel identity,
not trusted. If mismatched, report remains non-operational.

## Security boundary
These tests use scratch channels only and do not inspect, connect to, restart
or change installed GUI/IPC. PID+birth+same-user are helpful context, **NOT**
proof of GUI-loaded Python bytecode, authenticated in-process challenge or
actual effective peer token/ACL on installed pipe. G32 remains blocked.
Neither sample payload nor the helper can enable the deletion button.
No RAG queue/canary/catalog/journal or Stable changes.
