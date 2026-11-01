# RAG-DEL 01.04 DQ-E-F-15 - Private deletion path review contract (DEV, 2026-11-01)

## Goal
Conservatively validate an explicit set of private-project relative document
paths BEFORE any operational deletion confirmation. This DEV module performs
lexical checks only and NEVER opens or deletes a file.

## Additions
- rag/runtime/knowledge_deletion_selection_contract_dev.py
- tests/test_rag_del_01_04_dqef15_deletion_path_selection_dev.py
- This patch note
- Strict private project ID and <=500 explicit paths.
- Reject absolute, traversal, empty segments, duplicated/ancestor paths,
  casefold/NFKC aliases, Windows device names, ADS colon, Windows metachar,
  separators, dangerous format/control characters, trailing dots/spaces,
  excessive path or total UTF-8 length.
- Stable SHA-256 selection receipt bound to project and sorted paths; output
  contains no raw file paths.
- Windows lexical rules here are intentionally conservative, NOT an exact
  emulation of all filesystem names, reparse points or NTFS normalization.

## Non-negotiable boundary
No integration into running GUI or production preview, no queue/index/file
mutation, no real path resolution or source manifest attestation.
Even a fully valid selection still requires a pinned generation, source
inventory, real handle/provenance validation and separate user confirmation.
All operational flags are FALSE. G32 block remains.

## Verification
12 targeted tests for Windows aliases, reserved names, NTFS ADS, traversal,
Unicode spoofing, malformed input, private-ID constraint and no authorization.
## Verification
- Focused F15: 12 PASS.
- RAG-DEL 720 tests (714 PASS, 6 SKIP); RAG-AUTO 241 (236 PASS, 5 SKIP); MCP 12 PASS.
- Aggregate 973 total, 962 PASS, 11 SKIP, 0 FAIL.
- DEV-only. No installed/Stable, operational queue, live index, deletion or GitHub push.
