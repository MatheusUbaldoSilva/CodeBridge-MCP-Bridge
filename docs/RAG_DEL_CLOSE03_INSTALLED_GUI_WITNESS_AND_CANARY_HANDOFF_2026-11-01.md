# CLOSE-03 — Installed GUI and canary operational audit (2026-11-01)

Branch: dev-local. G32 status: BLOCKED (no operational deletion).
Operator approved DEV GUI integration/restart. No permission to infer a preferred
resolution for live newworldpvp canary from that approval.

## Installed GUI integration — verified on running Windows process

1. The one-shot read-only GUI witness was wired after window.show() in
   app_rewrite/ui.py, preserving the five inherited dirty files.
2. DEV process was restarted. Initial restart inherited QT_QPA_PLATFORM=offscreen
   from development test terminal: runtime READY, but no visible GUI.
   In-process witness on PID 13316 succeeded with native server PID, birth,
   fresh challenge, loaded rag_panel/review code method receipts and matching
   source hashes.
3. A controlled recovery checked CodeBridge executor active_job_id=null and
   command queue TOTAL=0, tried WM_QUIT, then terminated ONLY the two exact
   hidden/offscreen DEV process PIDs 13316/11076. It relaunched using the DEV
   pythonw.exe with QT_QPA_PLATFORM removed. Stable and launcher untouched.
4. Visible GUI now observed by native EnumWindows under process PID 13796,
   title CodeBridge 2.0 - MCP Bridge, IsWindowVisible true; CodeBridge READY.
5. Final DEV GUI witness on PID 13796 returned
   GUI_LOADED_CODE_KERNEL_PINNED_READONLY, blockers=[],
   challenge_bound=true, observed_server_pid=13796,
   expected_loaded_code_matches=true,
   installed_gui_loaded_code_observed=true,
   peer_accesscheck_observed=true.
   Actual client process token AccessCheck was performed against current GUI
   diagnostic pipe OWNER/GROUP/DACL; no ACL write or impersonation of GUI.
   Two loaded methods and source code paths matched exact in-memory SHA256:
   rag_deletion_review_panel.review_selected:
      530031e30d56a457c162f332e8905f0c1143461248e85261f92c1d78898fadd7
   rag_panel.review_authorization:
      2aa623b83e9333233091db3169501f97383e4312a9dccf5b21cf2002436c7c7d

## Live queue and canary rollback preconditions — read-only
- Upgraded rag/runtime/knowledge_deletion_operational_reconcile_dev.py to
  check exact auto-canary prior catalog backup path, journal schema/version,
  and public pointer SHA256 against the actual active-generation.json bytes.
- Regression test rejects even a structurally valid changed public generation
  pointer after canary activation.
- Installed read-only result: canary_catalog_consistent=true,
  canary_rollback_preflight_consistent=true, matched_canary_queue_job=true,
  1 pending approved READY_FOR_REVIEW in newworldpvp, 1 CANARY_ACTIVE,
  public generation v1_delta_1ae1d01ea84f4e unchanged.
- The rollback preflight merely verifies immutable identity/hash prerequisites;
  it is not a guarantee of no concurrent changes, and does NOT execute rollback.
- The existing rollback, if later approved by operator for this project/job,
  restores old catalog and can deactivate the newworldpvp active private index.
  Therefore it requires an explicit KEEP-vs-ROLLBACK-vs-RECONCILE decision.
  It must not be chosen automatically to artificially increase phase percent.

## Evidence boundaries, acceptance and tests
- The new installed witness verifies the dedicated diagnostic Named Pipe only.
  The real operational deletion-command pipe and its authorized state-changing
  contract are NOT implemented/attested. G32 retains
  installed_gui_operationally_attested=false,
  ipc_peer_effective_acl_attested=false,
  activation_authorized=false, operational_use_allowed=false.
- No RAG knowledge deletion, no queue promotion/cancel, no canary rollback, no
  index mutation, no Stable snapshot or GitHub push.
- Full RAG-DEL regression: 797 tests, 791 passed, 6 skipped, 0 failed.
- Functional acceptance remains 40%: CLOSE-01/02 complete; CLOSE-03 G32
  BLOCKED; CLOSE-04/05 gated.
- Never stage inherited dirty paths:
  app_rewrite/main.py, app_rewrite/rag_panel.py,
  benchmarks/rag017_code_only_extended_smoke.json,
  docs/RAG_017_J_VM_ROLLBACK_RUNBOOK_2026-10-10.md,
  rag/runtime/incremental_installed_queue_init.py.

## Next concrete decisions
A. Operator must decide explicitly to KEEP, ROLLBACK or RECONCILE the current
   newworldpvp RAG-AUTO canary. Re-validate queue, journal and hashes immediately
   before any authorized change. Rollback does not cancel READY_FOR_REVIEW.
B. Complete an authenticated, dedicated RAG deletion operational command
   channel with authorization bound to project, generation, selected file IDs,
   explicit user approval and effective peer token, plus recovery/rollback.
C. Test only disposable isolated private project before CLOSE-03 closure and
   CLOSE-04/05, then request separate Stable/GitHub publication authorization.
