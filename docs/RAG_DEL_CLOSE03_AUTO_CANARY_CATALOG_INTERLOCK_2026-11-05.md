# RAG-DEL CLOSE-03 — Shared AUTO-canary catalog interlock (scratch lab only)

Date: 2026-11-05. Branch: dev-local. NO installed GUI, live catalog,
production queue, source knowledge or Stable modifications.

## Technical finding
RAG-AUTO's auto-canary journal signs the SHA256 of the **whole**
project-indexes.json catalog (and pins the public pointer). RAG-DEL replacing
another private project's catalog entry would invalidate its active
newworldpvp canary journal even if private generations do not overlap.

## Implementation
- rag/runtime/knowledge_deletion_auto_canary_interlock_lab.py
  validates and inventories AUTO canary journals and their backups, with
  strict receipt identity, hash, public-pointer and old-catalog checks;
  protects against redirected journal/backup and orphan backups; refuses
  PREPARED/CANARY_ACTIVE on **any project**; accepts only exact ROLLED_BACK
  receipts whose old catalog SHA matches the current catalog.
  Reports a read-only result and grants no operational privileges.
- rag/runtime/knowledge_deletion_swap_lab.py
  applies the interlock inside the existing shared _catalog_mutex, BEFORE
  creating any RAG-DEL backup or journal, and repeats it after the locked
  validator immediately before any durable RAG-DEL writes.
  Retains the existing catalog CAS, PREPARED journal, injected pre/post-switch
  crash behavior and laboratory_rollback implementation.
- tests/test_rag_del_close_03_auto_canary_interlock_lab.py
  covers valid unrelated active/prepared canary (blocks), orphan/invalid
  journals (blocks), pointer/backup tamper (blocks), reconciled journal
  allowing a scratch catalog switch and recovery, an injected late canary
  inside the locked validator (blocks before writes), post-switch simulated
  failure + restoration with unchanged AUTO journal, and baseline no-AUTO
  switch/rollback success. Symlink test is skipped on Windows without
  symlink creation privilege.

## Results
- Scratch interlock module: 11 run, 10 pass, 1 skip, 0 fail.
- RAG-DEL full regression: 830 run, 823 pass, 7 skip, 0 fail.
- Scope is ONLY catalog within the OS temp scratch path; _lab_paths still
  forbids non-temporary catalogs and the API requires explicit lab flags.
- NO compatibility claim for catalog writes while a CANARY_ACTIVE journal
  exists. They remain blocked by design until the AUTO journal lineage
  protocol is expanded and independently verified, or the target canary is
  intentionally reconciled under its existing operator confirmation process.

## Next step
Independent cross-subsystem generation/recovery tests; then develop a
scratch-only journal-lineage proof for overlapping AUTO / RAG-DEL transitions.
Do not bypass the interlock to increase functional acceptance. CLOSE-03
remains BLOCKED G32, full functional acceptance remains 40%.
