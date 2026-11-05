# RAG-DEL CLOSE-03 — Admission-only DEV Named Pipe prototype

Date: 2026-11-05. Branch: dev-local. **NO operational deletion enabled.**

## Code changes
- rag/runtime/knowledge_deletion_operational_admission_dev.py:
  deterministic SHA256 binding of private project, source path selection and
  generation; rejects public project, traversal and malformed path segments
  (same relative-path grammar as the source preview), stale review,
  mismatching immutable review/catalog/public-pointer digests, lack of
  per-project/per-selection operator confirmation, failed GUI witness and
  pending AUTO jobs/canaries. Most importantly, **never trusts a client claim
  of an attested operational channel** and always reports
  OPERATIONAL_IPC_NOT_ATTESTED until a true production trust contract exists.
  All outputs force activation_authorized/deletion_enabled/
  operational_use_allowed to false, including forged positive receipts.
- rag/runtime/knowledge_deletion_admission_pipe_dev.py:
  one-shot independent NamedPipeServer on a strictly validated random
  UUID-named scratch pipe (never a live/known pipe); reads
  real native Windows connected client PID and client-process token AccessCheck
  against kernel descriptor. Only PRECHECK is permitted; DELETE/any other
  opcode is rejected before any candidate work. Trusted GUI and inventory
  readers are server-provided callbacks, NOT client-supplied JSON.
- tests/test_rag_del_close_03_operational_admission_dev.py:
  eight binding/expiry/public/traversal/canary/forgery tests.
- tests/test_rag_del_close_03_admission_pipe_dev.py:
  five cross-process actual Windows Named Pipe tests for kernel peer token,
  rejection of DELETE, forged client "operational_channel_attested",
  refusal of client-originated GUI/queue receipts, and refusal of real or
  predictable non-scratch pipe names.

## Tested
- Admission unit + cross-process scratch Named Pipe: 13 PASS.
- Full RAG-DEL: 810 run / 804 PASS / 6 SKIP / 0 FAIL.

## Runtime safety
The installed CodeBridge UI running today was independently identified as
**Stable Candidate 570bb17**, not DEV. Stable and launcher were NOT restarted,
rewritten, patched or touched. All code changes are dev-local source/tests.
Five pre-existing dirty paths remain excluded from staging.
No RAG index, canary, real queue, journal, GitHub push or production deletion.

## Gate
CLOSE-03 G32 remains BLOCKED. This scratch admission-only prototype is NOT a
production deletion IPC, and neither reviewer nor IPC has deletion actions.
CLOSE-01/02 completed: 40/100 functional acceptance. CLOSE-04/05 pending.

## Next
Build a real dedicated authenticated DEV GUI operational command protocol
with in-process secure identity and per-job immutable approval receipts,
transaction journal and rollback under a disposable/private canary.
Explicitly decide whether to KEEP, ROLLBACK or RECONCILE the existing
newworldpvp AUTO canary; never rollback another project's live index merely
to increment completion percentage. Stable remains untouched until a later
approved promotion.
