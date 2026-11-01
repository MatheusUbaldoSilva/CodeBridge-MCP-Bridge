# RAG-DEL 01.04 DQ-E-F-17 - Private project namespace alignment (DEV, 2026-11-01)

## Finding
The DEV-only F-15 explicit file selection review originally accepted
ASCII project identifiers up to 128 chars with limited excluded separators.
The actual private project router in
rag/runtime/isolated_project_index.py uses
PROJECT_ID_PATTERN = ^[a-z][a-z0-9_-]{1,63}$.
That mismatch allowed DEV receipts for IDs the real isolated router
would never enable, e.g. one-letter, uppercase, dotted or traversal-shaped IDs.

## Correction
- Changed F-15 review_explicit_deletion_paths_dev to import and apply the
  production router's shared PROJECT_ID_PATTERN.fullmatch, so there is
  a single source-of-truth namespace grammar in DEV.
- Explicitly retains the public CodeBridge project block.
- Added 11 focused F-17 tests for valid examples, uppercase/public aliases,
  path traversal, separators, malformed names, wrong lengths/types, exact
  router grammar and F-16 transitive rejection.
- Existing F-15 and F-16 unit suites still pass.

## Scope
No installed GUI/MCP/Stable changes, no production routing modifications,
no operational queue/index/catalog/filesystem reads or mutations,
no deletion and no GitHub push.

## Limits
A matching namespace pattern does NOT prove project existence, authorization,
source ownership, installed identity or safe filesystem paths. Final
manifest/generation verification and operator approval remain mandatory.
All F-15/F-16 operational permission fields stay False. G32 block remains.
## Verification
- F15/F16/F17 focused: 43 PASS.
- RAG-DEL: 751 tests, 745 PASS / 6 SKIP / 0 FAIL.
- RAG-AUTO non-MCP: 241 tests, 236 PASS / 5 SKIP / 0 FAIL.
- MCP-only: 12 PASS / 0 FAIL.
- Aggregate: 1004 tests, 993 PASS, 11 SKIP, 0 FAIL.
- Source-only changes; installed GUI/MCP/Stable/queue/index/GitHub not touched.
