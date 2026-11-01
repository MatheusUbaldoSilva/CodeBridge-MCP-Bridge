# CLOSE-03 G32 — Controlled operator decision for active RAG-AUTO canary

Date: 2026-11-01. Branch: dev-local. Audit-only; no operational changes.

## Observed source and state

- `rag/runtime/auto_index_promotion.py` exposes
  `disable_auto_canary(job_id, execute=False, operator_approved=False,
  confirmation=None)`. It requires *all* an explicit execute flag, operator
  approval and exact per-job confirmation.
- `rag/runtime/auto_index_canary.py:rollback_auto_canary` obtains a catalog
  mutex, validates journal identity and backup path, compares public pointer
  SHA256, verifies old catalog backup SHA256, then checks the current catalog
  matches journal new SHA256 before restoring previous catalog bytes.
- A successful rollback retains generation directories and backup, and reports
  `public_pointer_updated=False`. It does not cancel/approve the queue job.
- The read-only live reconciliation previously observed:
  private project newworldpvp, approved READY_FOR_REVIEW candidate and
  CANARY_ACTIVE journal, matching current catalog/backup hashes; public
  pointer v1_delta_1ae1d01ea84f4e remains unchanged.

## Decision branches (do not automate without authorization)

A. KEEP: If this isolated canary is intentional and still needed, keep active.
   Maintain G32 blocked for operations sharing the currently active catalog
   unless a separately approved, demonstrated safe isolation contract exists.
B. ROLLBACK: If the operator specifically chooses to disable the test canary,
   request separate explicit confirmation of the exact job and private project.
   Re-validate live catalog/backup/public pointer hashes and the isolated job
   immediately before any write. Then use the existing protected RAG-AUTO
   rollback mechanism; never directly replace catalog or delete snapshots.
   After rollback, re-inspect queue; READY_FOR_REVIEW may persist and still
   requires a distinct operator decision. Never silently cancel it.
C. RECONCILE: If it is a deliberate production-like review, preserve the
   canary until the correct separate RAG-AUTO review/promotion protocol is
   established. Do not infer auto-promotion from `approved=1`.

## Independent GUI/IPC blocker

Even B does NOT clear G32. Installed GUI in-process loaded-code identity and
actual connected Windows IPC peer token effective permissions remain unproved.
The scratch GetNamedPipeClientProcessId/birth-time check at commit 9dbdb4c
only proves kernel peer identity on a disposable pipe, not in installed GUI.
The production GUI delete button remains locked. Functional acceptance 40%.

## Required operator action before real change

An affirmative choice between KEEP, ROLLBACK or RECONCILE for the real
newworldpvp canary, and separate approval for any installed GUI restart,
in-process instrumentation and named-pipe security probing. The CodeBridge
development "Continuar" is not authorization to perform those actions.

No Stable or GitHub push is authorized by this decision record.
