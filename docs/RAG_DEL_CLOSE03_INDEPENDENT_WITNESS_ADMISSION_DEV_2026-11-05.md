# CLOSE-03 — Independent GUI witness wired into admission gate (DEV)

Date: 2026-11-05 | Branch: dev-local | Acceptance: 40% | G32: BLOCKED

## New isolated integration evidence

Added \`tests/test_rag_del_close_03_independent_attestation_admission_dev.py\`.
The test launches a separate offscreen GUI process with the actual DEV witness
server and loaded \`rag_panel\` / \`rag_deletion_review_panel\` modules. The
parent/test process independently pins PID and process creation time, connects
to the GUI witness, verifies the kernel-reported server PID, one-time challenge,
effective peer-token AccessCheck and loaded-code receipts against the modules
loaded by the child process.

The resulting verifier receipt is passed into
\`review_operational_deletion_admission\` together with a selection-bound
request, synthetic read-only queue inventory and a matching server-side
read-only review. The gate correctly does NOT report \`GUI_WITNESS_MISSING\`,
but still returns \`RAG_DEL_COMMAND_ADMISSION_BLOCKED\` with
\`OPERATIONAL_IPC_NOT_ATTESTED\`; all activation/deletion/operational flags
remain false. This proves independent GUI identity evidence reaches the
admission contract without being mistaken for per-request operational
authorization.

## Actual desktop process boundary observed (read-only)

The active CodeBridge GUI process inventory resolves to the Stable Candidate
snapshot \`570bb17\` (\`app_rewrite/main.py --no-elevate\`), not the
\`dev-local\` worktree. It was not restarted, patched, or used as a substitute
for DEV evidence. The DEV diagnostic integration remains opt-in and has not
been activated in the installed Stable process.

## Remaining G32 requirements

- A distinct, independently authenticated operational command IPC is still
  absent. A read-only witness/precheck is not a deletion command channel.
- Per-request operator approval must be independently bound to project,
  selected paths, review hash, catalog hash and public-pointer hash.
- Durable journal, locked catalog/generation CAS, crash recovery and rollback
  must be exercised only in a disposable private project.
- Live queue/journal/catalog/canary reconciliation and a decision for
  \`newworldpvp\` remain separate operational tasks. No automatic KEEP,
  ROLLBACK or RECONCILE is permitted.
- CLOSE-04/05 remain gated; no GUI delete action, Stable rollout or GitHub push.

## Test evidence

- New independent-witness-to-admission integration: 1 PASS.
- It exercises a separate GUI child and external verifier parent; no real
  RAG queue/index/catalog is read or mutated.
- Previous RAG-DEL baseline before this added test: 837 run, 830 PASS,
  7 SKIP, 0 FAIL. Re-run the complete suite before commit.

