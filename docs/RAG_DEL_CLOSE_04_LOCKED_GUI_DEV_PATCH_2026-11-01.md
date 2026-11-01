# PATCH NOTES — RAG-DEL CLOSE-04 UI locked shell (DEV)

Date: 2026-11-01
Branch: dev-local
Scope: non-destructive user interface preparation only.

## Changed
- app_rewrite/rag_deletion_review_panel.py
  - Added a visible "Excluir conhecimentos" button, permanently disabled.
  - Added a clear explanation of CLOSE-03 missing authorization.
  - Project switches, preview success, and preview errors never enable the action.
  - Public project remains ineligible.
- tests/test_rag_del_close_04_locked_gui_dev.py
  - Tests default lock, malicious preview flag, project reset and preview failures.

## Verification
- New GUI tests: 2 passed.
- Existing Qt review tests: 4 passed.
- Candidate deletion staging tests: 8 passed.
- Full RAG-DEL test suite: 772 run; 766 passed, 6 skipped, 0 failed.

## Limitations
This is *not* a CLOSE-04 acceptance completion. No deletion callback,
confirmation, generation cutover, operational journal modification or
permissions change was implemented. CLOSE-03/G32 still blocks operational
activation. Installed/stable code, live RAG and original data were not touched.
Five pre-existing dirty paths remain excluded from the commit.
