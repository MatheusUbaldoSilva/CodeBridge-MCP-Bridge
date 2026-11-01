# RAG-DEL 01.04 DQ-E-F-18 - Real preview with synthetic SQLite (DEV, 2026-11-01)

## Objective
Prove that the F-16 preview-selection consistency reviewer accepts the
**actual** RAG-DEL-01.02 preview response schema instead of relying solely
on handcrafted dictionaries. Use the pre-existing synthetic SQLite and
manifest fixture from tests/test_rag_del_01_02_preview.py.

## Implementation and scope
- Added tests/test_rag_del_01_04_dqef18_real_preview_synthetic_index_dev.py.
- Reuses the synthetic test fixture by invoking only its setUp via a
  module import (avoids unintentionally rediscovering original tests).
- Calls preview_knowledge_removal() against temp SQLite and mocked project
  resolver / manifest. No live RAG catalog, installed GUI or index touched.
- Passes returned preview data directly to the F-16 read-only checker.
- Tests all consistent fields on full and partial selection; stale
  caller-expected generation/revision; hash tampering; selected path
  mismatch; false operational flags; no database writes.
- Documents the temporal-gap limitation explicitly: after synthetic DB
  mutation, a previously captured preview can still have a valid digest,
  while a **fresh** preview rejects a broken index inventory. A digest does
  not prove the index is still unchanged at execution time.

## Safety
All installed GUI/IPC process attestations are pending; F-16 remains
non-authorizing, source_only=true, operational_use_allowed=false.
No queue/journal/production file inspection, mutation, deletion or push.
G32 block remains. The original five dirty files remain untouched.

## Verification
11 focused F-18 tests, synthetic SQLite in TemporaryDirectory.
## Verified
- Focused F16 + F18: 31 PASS.
- RAG-DEL 762 tests: 756 PASS, 6 SKIP, 0 FAIL.
- AUTO non-MCP 241 tests: 236 PASS, 5 SKIP, 0 FAIL.
- MCP 12 PASS.
- Total: 1015 tests, 1004 PASS, 11 SKIP, 0 FAIL.
- Strictly synthetic temp SQLite; no operational RAG read/write.
