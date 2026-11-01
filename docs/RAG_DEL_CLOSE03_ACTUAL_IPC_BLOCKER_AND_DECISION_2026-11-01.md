# RAG-DEL CLOSE-03 — runtime integration decision record

Date: 2026-11-01
Branch: dev-local
Scope: bounded, source-only evidence + isolated MCP test-runner validation.
Status: CLOSE-03 BLOCKED; no operational activation.

## Concrete findings

1. The actual RAG GUI route is in app_rewrite/rag_panel.py and
   app_rewrite/rag_deletion_review_panel.py. It only calls
   build_deletion_review() and exposes a permanently disabled delete button.
   No operational delete command, trusted installed GUI handshake or queue
   transition is wired to this panel.

2. The general Windows control transport exists in
   app_rewrite/windows_control_channel.py and app_rewrite/ipc_named_pipe.py.
   NamedPipeServer.accept() creates a pipe using FIRST_PIPE_INSTANCE and
   a protected current-user SID DACL. build_current_user_pipe_sddl() grants
   GA to the current SID with a Medium integrity label. This proves only
   source intent, not an effective ACL for the installed process, nor
   peer process identity or a dedicated RAG deletion authorization channel.

3. rag/runtime/knowledge_deletion_effective_accesscheck_dev.py checks
   native Windows AccessCheck on scratch pipe handles with the CURRENT
   process's impersonation token. It does not examine a trusted installed
   GUI peer or operational handle; it must not be counted as CLOSE-03 passed.

4. Source-level review helpers under rag/runtime/knowledge_deletion_*_dev.py
   expressly report non-operational readiness. Offline HMAC challenges,
   PID strings, own-process tokens and static SDDL alone cannot prove
   installed code, process birth, actual peer token permissions or queue
   safety.

5. The prior 3 missing MCP test modules were successfully executed
   WITHOUT installing dependencies, using the existing interpreter:
   author_mcp/.venv/Scripts/python.exe
   - test_rag_auto02_mcp_launch.py
   - test_rag_auto03_mcp.py
   - test_rag_auto_mcp_tools.py
   Result: 12 tests run, 12 passed, 0 skipped, 0 failed.
   The GUI test runtime remains CodeBridge-Runtime/dev (with PySide6).

## Exact remaining operational evidence (separately authorized)

A. Trusted in-process identity of the *installed, running GUI*: pinned
   process creation time, executable, loaded code and authenticated
   challenge/response; do not trust caller-supplied hashes as identity.
B. Verify native Windows effective ACL/peer token against the actual
   permitted IPC object, including process/session boundary and ownership.
   Same-user SID permission is not per-process authentication.
C. Authorized read-only inventory of actual operational queue + journal,
   alongside pinned active generation, pending transactions and rollback
   preconditions. Do not mutate queue, journal or production index.
D. Keep G32 fail-closed until A+B+C have trustworthy evidence. Only then
   separately authorize an isolated disposable-project pilot.

## Acceptance and restrictions

CLOSE-01 and CLOSE-02 complete: 40/100 points.
CLOSE-03 remains 0/20; CLOSE-04 and CLOSE-05 remain 0/20.
No changes to live GUI, IPC permissions, RAG stores or Stable.
No approval for deletion or GitHub push is implied by this document.

Next action: conduct A+B+C only with separately approved operator scope,
record real process/ACL/queue evidence, then decide whether CLOSE-03 can pass.
Do not add arbitrary new sub-phases while the same blocker is unresolved.
