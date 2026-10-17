# RAG-LAB.02-A - Synthetic three-store file tree catalog (2026-10-17)

State: LAB ONLY. NOT production backup authorization.

## Work
- Added rag/runtime/offline_store_tree_catalog.py for SQLite, manifest and every Qdrant file in the synthetic root.
- Scans two times; compares catalog, sizes and SHA-256; rejects new/deleted/mutated files observed between the passes.
- Explicit rejection of SQLite WAL/SHM/journal, redirected paths/junctions/symlinks, hardlinks, invalid types and missing stores; bounded files and bytes.
- Added tests/test_offline_store_tree_catalog.py: 8 focused tests, including synthetic concurrent file creation and invalid paths.

## Validation
- Focus: 8 PASS.
- Full regression: 83 generation + 196 offline + 7 preflight + 38 incremental = 324 PASS, exit 0.
- Previous lab Qt preview 7 PASS.
- All reports retain copy_authorized=false, all_handles_closed=false and production_quiescence_proven=false.

## Limits
Two sequential scans are NOT atomic, and filesystem hash stability does not prove that Windows file mappings, writers or mmap consumers have exited. This module does not stop processes, lock real files or copy production indices.

Next: RAG-LAB.02-B - SQLite native handle and WAL/SHM/journal tests in dedicated synthetic child processes, then RAG-LAB.02-C through H.
