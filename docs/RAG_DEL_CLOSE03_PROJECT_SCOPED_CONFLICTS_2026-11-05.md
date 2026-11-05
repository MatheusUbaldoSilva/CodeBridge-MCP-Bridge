# CLOSE-03 — Scoped private-project conflict inventory (read-only)

Date: 2026-11-05. Branch: dev-local.

## Discovery on the actual Windows installation
- Two isolated private catalog projects exist: codebrige-mcp-rag and newworldpvp.
- The only READY_FOR_REVIEW RAG-AUTO job and CANARY_ACTIVE belong to newworldpvp.
- Their generation directories are distinct. The codebrige-mcp-rag project has
  zero own queue jobs and zero own canaries; newworldpvp has one each.
- The shared catalog and public pointer retain the hashes observed during the
  read-only inventory. **No rollback was performed or required to plan.**
- A third project not present in the catalog was rejected; no project created.

## Code
- rag/runtime/knowledge_deletion_project_conflicts_dev.py:
  owner-independent read-only inventory with SQLite URI mode=ro and
  PRAGMA query_only=ON. Checks distinct existing generation directories;
  canonical project IDs, target-vs-unrelated queue and canary scope;
  active canary journal, backup SHA256, exact catalog pointer hashes,
  target queue state and repeated queue/catalog/pointer checks.
  Reports TARGET_CONFLICTS_CLEAR_FOR_READONLY_PLANNING only if target
  has no active queue/canary, all relevant hashes reconcile, and
  generation directory has no overlap. Never authorizes deletion.
  Shared catalog compare-and-swap under canonical lock is REQUIRED on any
  future mutation, even when other projects' canaries are unrelated.
- rag/runtime/knowledge_deletion_operational_admission_dev.py:
  optional server-provided target_conflicts receipt (not client-supplied);
  if target-specific scope passes and catalog/public-pointer digests match,
  treats an unrelated queue/canary as not blocking **read-only planning**.
  Does not change OPERATIONAL_IPC_NOT_ATTESTED veto or permit deletion.
- rag/runtime/knowledge_deletion_admission_pipe_dev.py:
  optionally invokes get_project_conflicts(project_id) on the server side
  only, never trusting GUI or project-state data supplied in the JSON.

## Tests
- 7 synthetic project-scope tests pass: unrelated canary read-only planning,
  active same-project job blocks, mutated public pointer blocks, tampered
  rollback backup blocks, overlapping generation dirs block, unknown target
  blocks, missing queue blocks.
- Added 2 admission tests for scope mismatch and server-owned observer only.
- Full CLOSE-03 DEV pattern: 44 PASS.
- Full RAG-DEL: 819 run, 813 PASS, 6 SKIP, 0 FAIL.

## Boundaries
- Installed Stable Candidate 570bb17 remained open and untouched.
- Live newworldpvp canary and queue are preserved.
- No index, journal, source file, GUI production, Stable or GitHub changes.
- The read-only inventory cannot prove the future atomic shared catalog
  CAS or the actual state-changing deletion IPC. G32 CLOSE-03 remains
  BLOCKED, functional acceptance 40%.
- Next implementation target is an isolated-project **atomic catalog CAS
  transaction** in a scratch store with preservation of unrelated projects
  and recoverable rollback, before the real DEV GUI delete button is enabled.
