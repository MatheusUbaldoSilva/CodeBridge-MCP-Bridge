# RAG-LAB.01-G - Fechamento do laboratorio de processos (2026-10-17)

Status: RAG-LAB.01 A-B-C-D-E-F-G LABORATORY COMPLETED. NOT production approved.

## Evidence matrix - dividir para conquistar
- 01-A (931cf84): sample clock, stable PID scope and identity contract.
- 01-B (46471d5): scoped CIM observer and lab-only standalone CLI; sanitized fingerprints.
- 01-C (03cf8a8): temporal parent-child lineage, birth ordering and PID identity.
- 01-D (1e39b20): orphan, late spawn, parent PID changes and negative coverage.
- 01-E (d9d62c2): bounded observation windows, two final absence samples, freshness, no PID reappearance.
- 01-F (336d6ce): fail closed on CIM timeout, malformed JSON, permissions, partial identities, reversed clocks and oversized output.
- 01-G: added tests/test_offline_lab01_integrated_contract.py, 3 integrated tests verifying observer -> timestamp contract -> lineage -> exit window, including late child and incomplete CIM identities.

## Validation and closure
- New integrated contract: 3 PASS.
- Final full regression: 83 generation, 188 offline, 7 preflight and 38 incremental = 316 PASS.
- Qt preview offscreen: 7 PASS. Total 323 tests, exit 0.
- git diff --cached --check and selective stage only.
- Two prior dirty files are NOT part of this phase:
  benchmarks/rag017_code_only_extended_smoke.json (modified);
  docs/RAG_017_J_VM_ROLLBACK_RUNBOOK_2026-10-10.md (untracked).
- Checkpoint and remote audit required after commit.

## Boundary of evidence
This phase proves only the identity and exit observations for scoped SYNTHETIC Windows processes. It does NOT discover all live GUI/MCP/indexer descendants or certify mmap/SQLite/Qdrant handle release in production. Output remains copy_authorized=false, production_quiescence_proven=false and all_handles_closed=false.

## Next milestone
RAG-LAB.02-A - full lab-only catalog of SQLite, manifest and Qdrant file trees, including reparse/hardlinks and concurrent create/delete. RAG-LAB.02-B through H stay open. No real backup or shutdown.
