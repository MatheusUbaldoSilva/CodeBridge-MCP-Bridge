# PATCH NOTES — RAG-DEL CLOSE-03 native AccessCheck scratch DEV

Date: 2026-11-01
Branch: dev-local

## Scope and impact
- New rag/runtime/knowledge_deletion_effective_accesscheck_dev.py
  - Invokes Windows native AccessCheck against an open test-owned pipe fd.
  - Reads OWNER/GROUP/DACL from the real kernel security descriptor.
  - Duplicates a query-only current process token to an impersonation token.
  - Closes all temporary handles and frees the security descriptor.
  - Restricts requested access masks to a small explicit allow-list.
  - Fails closed on bad fd, null DACL, query failures or invalid access masks.
  - Returns denied/allowed only as observations, never as operational permission.
- New tests/test_rag_del_close_03_native_accesscheck_dev.py
  - 7 tests against native scratch objects plus failure paths.

## Evidence
- 7 targeted tests PASS.
- RAG-DEL regression 779 executed / 773 passed / 6 skipped / 0 failed.
- No installed GUI, live queue, journal, permissions, generation, RAG store
  or Stable contents inspected or changed.
- No operational trusted process/loaded-code evidence is claimed.

## Acceptance
CLOSE-03 remains BLOCKED: this test only proves that a real Windows API
can evaluate the current token on test-owned handles. It does not prove
effective access for the installed GUI's peer token or pipe, and is not
a substitute for authorized IPC/queue/journal/operator validation.
G32 safeguard remains intact; progress = 40%, NOT increased.
