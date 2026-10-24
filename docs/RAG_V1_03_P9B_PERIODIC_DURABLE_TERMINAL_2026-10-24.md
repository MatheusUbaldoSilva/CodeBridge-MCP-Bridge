# P9-B.03-B — Periodic Windows Task Scheduler plus durable terminal gate
Date: 2026-10-24
Status: disposable scratch-lab CERTIFIED FOR THREE INVOCATIONS ONLY.
P9-B remains OPEN. No actual unified NSIS recovery or trusted publisher root.

## Evidence
Independent real Windows Task Scheduler periodic worker with a one-minute repetition:
1) first invocation reserved transaction attempt=1 in OS-sidecar-locked fsync retry ledger, wrote first.json, hard exited os._exit(87).
2) separate second scheduled invocation reserved attempt=2, persisted TERMINAL under the same exclusive lock and atomic ledger replacement, wrote done.json.
3) separate third scheduled invocation was denied by reserve_disposable_retry with state P9B_RECOVERY_ALREADY_TERMINAL, reason DURABLE_TERMINAL_STATE, wrote third.json. Ledger attempts remained 2, state TERMINAL. Three process IDs checked distinct as supported by marker evidence. Scheduler LastTaskResult 0 and XML repetition true.
Live result: PERIODIC_DURABLE_TERMINAL_VERIFIED, persisted_attempts=2, three_distinct_invocations=true, production_modified=false.
This is an isolated TEMP mock recovery. No public NSIS installer or official registry keys were touched.

## Source changes
installer/rag_p9b_recovery_retry_ledger.py: add idempotent mark_disposable_retry_terminal under same OS lock and atomic fsync replacement, fail closed without postverify, require bound SHA and recorded attempt, refuse future reservations after TERMINAL. Existing retry budget max3 remains unchanged.
installer/p9b_scheduler_durable_terminal_lab.ps1: true periodic Windows Task Scheduler standalone worker, three distinct real invocations and fail-closed evidence assertions, task/scratch finally cleanup.
tests/test_rag_p9b_recovery_retry_ledger.py: four additional terminal tests (existing 9 retained), 13 PASS.
tests/test_rag_p9b_scheduled_durable_terminal_lab.py: five PowerShell safety/contract tests PASS.
Full P9B 577 tests PASS in 51.916 seconds.

## Remaining
Hard crash during journal terminal atomic rename and parent-dir durability policy, same-user filesystem tamper, and automatic task cleanup after a terminal are NOT yet certified as independent transaction recovery. The PowerShell harness deregisters the task; a future standalone supervisor must perform its own terminal-safe cleanup. Producer authentication 01C remains TRUST_ROOT_UNVERIFIED. Need single actual NSIS journal for 236 originals/22 new/5 shortcuts/2 scoped HKCU and explicit production operator authorization for any live cutover.