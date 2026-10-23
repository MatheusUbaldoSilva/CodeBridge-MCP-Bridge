# P9-B ? Independent Scheduled Task disposable rollback lab

Date: 2026-10-23. State: LAB VERIFIED / PRODUCTION CUTOVER BLOCKED.

After recovering CodeBridge CBMCP/1 READY, the project staged a
hash-identical four-artifact identity into an independent stage. A
read-only scheduled Windows task returned SCHEDULED_READONLY_LAUNCH_VERIFIED.

A second existing guarded launcher
installer/p9b_scheduled_combined_lab.ps1 was then executed.
It created a disposable Windows Scheduled Task that ran the project's
fixed set of temporary recovery tests in an external Python process.

Result: SCHEDULED_COMBINED_LAB_VERIFIED
- tests: 3
- ancestry_verified: true
- production_modified: false
- nsis_executed: false

The test suite covers detached combined hardcrash recovery and isolated
HKCU scratch/file recovery. Temporary task and worker directories were
verified absent after completion. This is evidence of an independent
process in a DISPOSABLE LAB only, not a real production rollback.

Earlier regressions in this session: 483 P9-B tests PASS, 65 runtime PASS,
12 additional focused rollback tests PASS. No actual installer execution,
real GUI/MCP shutdown or RAG public generation swap was performed.

P9-B remains OPEN until a durable independent mutating supervisor,
process stop/poststop certification, full real rollback testing in a
controlled installed environment, and post-update CBMCP/1 plus queue/RAG
reconnect evidence are validated. Operator authorization must precede
any live production cutover. Preserve three original local dirty files.
