# P9-B.03 — Real scoped HKCU scheduled retry startup diagnostic

Date: 2026-10-24
Status: FAILED / NOT CERTIFIED — P9-B OPEN

Baseline before experiment: 099d1c5, synchronized to origin.
The experimental test only used TemporaryDirectory fixtures, a new uniquely named Task Scheduler task and scoped-HKCU remapping; it did not target installed CodeBridge, official HKCU keys or live RAG.

A genuine Windows scheduled test tried to execute the existing run_lab_retry against the existing 236 original + 22 new file snapshot, 5 shortcuts and 2 actual isolated HKCU mappings. The normal direct adapter test had previously passed. The scheduled version failed before its first visible Python worker marker.

Observations from bounded 12s and 45s runs:
- Task Scheduler registration and Start-ScheduledTask returned successfully.
- Task action inspection confirmed Python313 executable and an absolute TEMP bootstrap .py argument.
- LastTaskResult=2 with direct Python action; command-wrapper attempt returned 1.
- Worker first boot marker was absent, so reservation, rollback and terminal were NOT proven.
- Static py_compile of generated worker succeeded.
- Tests exited FAILED and cannot be counted as certified passing regression.
- Temporary task cleanup ran. This experimental test source was intentionally discarded instead of committing a failing certification test.
- This does not prove that the actual Python worker entered, that NSIS ran or that a durable retry completed.

Next experiment: compare a minimal known-working scheduled Python action with this exact TEMP fixture path, inspect execution context and capture interpreter-level stderr before any module import. Only once startup is proven attempt the scoped-HKCU retry under a single journal. Never relax the trust-root or production authorization gates.

Protected unrelated dirty files remain outside this change.
