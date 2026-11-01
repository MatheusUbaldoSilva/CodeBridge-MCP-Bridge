# RAG-DEL 01.04 DQ-E-F-16 - Preview/selection binding contract (DEV, 2026-11-01)

## Rationale
F-15 checks lexical safety of a private-file selection. The existing
RAG-DEL-01.02 read-only preview returns project, selected paths, generation,
source revision, document/chunk counts and a canonical SHA-256 review hash.
F-16 compares those contracts **using caller-supplied diagnostic records**.

## Implementation
- New rag/runtime/knowledge_deletion_preview_binding_dev.py.
- Requires an exact read-only preview field set matching
  rag/runtime/knowledge_deletion_preview.py.
- Re-creates the existing preview hash from all ten source fields,
  with JSON sorted keys, UTF-8 and ensure_ascii=False.
- Compares the exact sorted file selection, project identifier,
  document removal count, and caller-supplied expected generation
  and source revision.
- Rejects non-boolean/mutated or true operational flags, unknown fields,
  malformed version labels, invalid counts and digest formats.
- A missing expected version intentionally fails closed.
- Reports SHA-256 receipts but does not expose raw file names.
- 20 adversarial unit tests cover positive mock, stale versions, mismatched
  project/paths/counts/hash, forged authorization, absent/invalid fields,
  invalid selection and no mutation.

## Security boundary
No filesystem, index, manifest, SQLite, Qdrant, live GUI or IPC is read.
Even a fully coherent caller-supplied preview or recomputed SHA-256 is NOT
an authenticated fresh preview. Caller-supplied version labels are NOT
independently pinned installed generations. The review always reports
preview_origin_authenticated=false, current_generation_attested=false,
ready_for_operational_pilot=false, activation_authorized=false and
operational_use_allowed=false.

G32 safety restriction and separate installed-GUI/token/ACL validation
requirements remain. No installed/Stable modifications, no live deletions
or GitHub push. The original five dirty paths are outside this phase.

## Remaining prerequisites
An explicitly approved trusted process/reader identity channel, OS-effective
IPC permission verification, separately approved operational queue/journal
audit, pinned generation evidence and final operator confirmation.
## Verified regression
- F15+F16 focused: 32 PASS, 0 FAIL.
- RAG-DEL: 740 tests, 734 PASS, 6 SKIP, 0 FAIL.
- RAG-AUTO non-MCP: 241 tests, 236 PASS, 5 SKIP, 0 FAIL.
- MCP-only: 12 PASS, 0 FAIL.
- Aggregate: 993 tests, 982 PASS, 11 SKIP, 0 FAIL.
- No installed GUI, Stable, GitHub, live queue or index modification.
