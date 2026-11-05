# CLOSE-03 — DEV GUI opt-in diagnostic IPC and one-time challenge

Date: 2026-11-05 | Branch: dev-local | G32: **BLOCKED** | Acceptance: **40%**

## Scope and integration

- \`rag/runtime/knowledge_deletion_gui_admission_dev.py\` adds a one-shot,
  read-only PRECHECK server inside the *DEV GUI process*, but **only when**
  \`CODEBRIDGE_RAGDEL_DEV_ADMISSION_DIAGNOSTIC=1\` is explicitly present.
  Without the opt-in no extra admission listener is created.
- \`app_rewrite/ui.py\` invokes the optional diagnostic after \`window.show()\`,
  alongside the existing loaded-code witness, without changing the delete
  button, existing control channel, Stable snapshot, or RAG data.
- It reuses the previously tested scratch-only Named Pipe server and
  native Windows client PID / process token AccessCheck. The server creates
  a fresh randomized scratch pipe name and accepts one request only.
- Operational inventory and project conflict reports are read with
  existing read-only services on the *server* (never trusted from the client).
- The DEV GUI also invokes the actual build_deletion_review(project_id,
  selected_paths) server-side, exclusively in read-only mode. Its reviewed
  project, selected paths, generation and review_sha256 MUST match the client
  request; execution_enabled and source_files_modified MUST be false.
  A source read failure or mismatch fails closed as
  SERVER_READ_ONLY_REVIEW_MISMATCH. Test injection of a fake server-side
  review is allowed only in isolated offscreen test processes.
- The GUI witness input to this diagnostic is intentionally
  \`GUI_WITNESS_NOT_ATTESTED\`: the GUI cannot declare its own identity
  securely by returning fields in its own response. The diagnostic is
  **not an operational authorization route** and cannot activate deletion.

## Request challenge (V1)

1. Validate the connected client process identity and effective read access
   against the actual scratch kernel pipe descriptor.
2. Server sends \`RAG_DEL_ADMISSION_PRECHECK_CHALLENGE_V1\` with 256-bit
   fresh random nonce.
3. Client responds with \`RAG_DEL_ADMISSION_PRECHECK_REQUEST_V1\` including
   the exact nonce, \`PRECHECK\` operation and selection-bound request.
4. Any reused/mismatched challenge is rejected BEFORE GUI or queue readers
   run. Unknown operations (including \`DELETE\`) and client-supplied
   GUI/queue attestation receipts are refused.
5. Server sends a read-only, fail-closed result and expects explicit
   \`CLOSE\` handshake. Regardless of the inputs, all outputs enforce
   \`activation_authorized=false\`, \`deletion_enabled=false\` and
   \`operational_use_allowed=false\`.

This is a disposable DEV precursor, **not** an installed operational
state-changing channel. The existing project-specific state and
AUTO-canary catalog journal global pin still block catalog writes.

## Evidence

- \`tests/test_rag_del_close_03_gui_admission_dev.py\` exercises separate
  offscreen GUI and client processes, kernel server PID, native peer token,
  opt-in behavior, DELETE rejection and client-spoofed receipts.
- \`tests/test_rag_del_close_03_admission_pipe_dev.py\` was updated to
  the one-time challenge protocol and rejects a deliberately stale nonce
  before any state observer executes.
- CLOSE-03 DEV suite: 48 PASS before the additional review-binding test.
  The new GUI process SHA-mismatch regression also passes.
- RAG-DEL 01.04 suites: 634 tests, 630 PASS and 4 SKIP.
- Admission Named Pipe transport suite now includes malformed request and
  observer-failure cases: **9 PASS**. Malformed request bodies are rejected
  before GUI, queue, project-conflict or server-review observers execute;
  a failed GUI witness observer produces a structured fail-closed receipt.
- Complete RAG-DEL regression after input-hardening:
  **840 run / 833 PASS / 7 SKIP / 0 FAIL**.
- Live queue/canary/journal read-only evidence is recorded separately in
  \`RAG_DEL_CLOSE03_OPERATIONAL_RECONCILIATION_2026-11-05.md\`.
- Qt's missing bundled-font warning remains nonfatal.

## Boundaries / next steps

No Stable restart, no installed DEV restart, no installed production GUI
mutation, no RAG queue/canary/catalog/index change, no GitHub push.
Five inherited dirty local paths remain untouched.

The current full acceptance remains at 40%, CLOSE-03 G32 blocked. To enable
real deletion eventually, create independently authenticated per-request
authorization plus durable journal and locked generation/catalog CAS, with
selected-file review binding and operator confirmation, then verify rollback
in a disposable private project. Preserve the live newworldpvp canary unless
a separate explicit target-specific decision resolves it.
