# RAG-DEL - CLOSE-01 and CLOSE-02, objective delivery gates (DEV, 2026-11-01)

## Why the former 87% plateau was misleading
The prior 87-90% was a subjective technical-maturity estimate, not proof
that installed deletion was working. This new score covers FIVE equal-weight
functional acceptance gates (20 points each). Equal weights are an explicit
tracking convention, not a prediction of remaining effort or schedule.
Only completed, evidenced gates contribute to the score.

## CLOSE-01: real blocker audit - COMPLETE (20/20)
- app_rewrite/rag_deletion_review_panel.py is a read-only preview widget.
- app_rewrite/rag_deletion_selector.py emits preview, not deletion.
- Independently trusted installed GUI process/module attestation is missing.
- Actual Windows effective IPC access and token isolation not verified.
- G32 is a remaining gate, not a target for circumventing controls.
- Operator-approved operational queue/journal and generation reconciliation
  has not occurred. These are bounded delivery blockers rather than an
  invitation to infinite additional simulation phases.
- No operational UI delete action and no Stable homologation.

## CLOSE-02: actual candidate preparation in disposable lab - COMPLETE (20/20)
- Added tests/test_rag_del_close_02_preview_to_staging_lab.py.
- Temporary SQLite/FTS and manifest contain alpha.py, bravo.py, charlie.py.
- Actual preview_knowledge_removal() plus F16 consistency review.
- Actual stage_removal_sqlite_manifest() creates a NEW isolated candidate.
- Confirms alpha.py absent from candidate documents, chunks, FTS, manifest;
  bravo.py and charlie.py remain unchanged with original content.
- Two-file removal test, stale digest, generation change, existing stage
  destination, public project refusal, and full source SHA-256 retention.
- Uses independent Qdrant scratch source/target and verifies a surviving
  vector copy, durable checkpoint and candidate consistency.
- Original source and public pointer are never modified or activated.
- This proves preparation of a *candidate*, not approved operational cutover.

## CLOSE-03: installed identity and operational preflight - BLOCKED (0/20)
Needs an explicitly authorized and authenticated in-process installed GUI
identity/loaded-code channel, independent Windows effective IPC AccessCheck
and token isolation, operator-approved read-only queue/journal checks and
pinned active-generation/rollback preconditions. G32 remains intact.
An offline HMAC simulation and SHA-256 over caller data are NOT sufficient.

## CLOSE-04: delete action, operator confirmation, rollback UI - NOT STARTED (0/20)
Only after CLOSE-03 passes: confirm selected knowledge removal, recheck the
preview/generation, build and verify staged generation, ensure safe rollback,
journal the result and display completion/errors. Source files must not be
deleted: this workflow removes indexed knowledge only.

## CLOSE-05: controlled pilot and Stable - NOT STARTED (0/20)
Operator-approved disposable/private-project pilot, retrieval checks on
selected versus preserved documents, rollback/recovery, regression and
homologation before separately approved Stable update and GitHub push.

## Measured delivery
- Completed gates: 2 of 5.
- Functional acceptance: 40 / 100 points = 40%.
- Installed GUI operational deletion: DISABLED.
- Stable production homologation: NOT DONE.
- 40% is a stricter new functional score, not a regression from subjective
  87% prior code-maturity assessment.
- Never advance a score merely because another test or file was created.

Machine-readable source: docs/RAG_DEL_CLOSEOUT_ACCEPTANCE_V1_2026-11-01.json.
Original five uncommitted files protected. Code only in dev-local.
## Executed tests and outcome (DEV)
- Closing integration (8 new + 1 prior candidate E2E + 4 Qt review): 13 PASS.
- RAG-DEL full: 770, of which 764 PASS / 6 SKIP / 0 FAIL.
- RAG-AUTO non-MCP: 241, of which 236 PASS / 5 SKIP / 0 FAIL.
- MCP: 12 PASS / 0 FAIL.
- Aggregate full regression: 1,023 tests, 1,012 PASS, 11 SKIP, 0 FAIL.
- No live RAG data access or delete. Source files always retained.
- Functional acceptance scoring: two of five 20-point gates = 40%;
  installed operational deletion remains disabled.
