# P9-B.03-B - Real Windows Task Scheduler periodic scratch worker retry
Date: 2026-10-24
Status: PERIODIC AUTO-RETRY OBSERVED in disposable scratch lab only.
P9-B remains OPEN; this is NOT native RestartCount proof or unified NSIS recovery certification.

## Evidence
Independent Windows Scheduled Task test started by One-Time trigger with 1-minute repetition. Worker wrote fsynced first.json and terminated os._exit(87). Task Scheduler LastTaskResult became 87 (Ready). Despite XML RestartCount 2 / RestartInterval PT1M, native failure restart did NOT run in preceding 225-observation baseline; see previous blocker e2f4df8.

With the additional Repetition trigger, without manually re-running the worker, a distinct scheduled invocation wrote done.json; LastTaskResult changed to 0. Observed: xml_trigger=true, xml_restart_count=true, xml_restart_interval=true, xml_repeat=true, first_exists=true, second_exists=true, production_modified=false, state=PERIODIC_AUTO_RETRY_OBSERVED. This only proves periodic task invocation and recovery of a trivial marker; the first and second PIDs must be recorded and compared as part of future integration certification.

Cleanup independently verified: LEFTOVER_TASK=False, LEFTOVER_FOLDERS=0. Operational event log was left unchanged. No production NSIS/HKCU/RAG change.

## Reproducible implementation
installer/p9b_scheduler_restart_diagnostic_lab.ps1: isolated TEMP Python worker and registration; 165 observations max, data captured while task runs, cleanup in finally; explicit refusal if there is no second execution or zero exit status. tests/test_rag_p9b_periodic_scheduled_retry_contract.py: five PowerShell parser/contract checks PASS.
Full P9B regression: 568 tests PASS in 53.180 seconds.

## Remaining integration requirements
- Bind scheduled retries to trusted frozen transaction identity and OS-locked 3-attempt retry ledger.
- Do not replay after terminal state; task must not reapply rollback after completion, and must clean up only when terminal state is fsync durable.
- Before actual NSIS use, require independent protected trust anchor and true single journal across 236 old/22 new files, 5 shortcuts, 2 HKCU lab keys, and recovery from supervisor hard exits.
- Never treat a recurring trigger plus test-marker success as certification of official production cutover.