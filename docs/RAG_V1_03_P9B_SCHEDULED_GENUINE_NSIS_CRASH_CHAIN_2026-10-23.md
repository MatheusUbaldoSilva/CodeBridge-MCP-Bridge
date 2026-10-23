# P9-B - scheduled genuine isolated NSIS crash chain
Status: LAB PASSED, P9-B OPEN
Date: 2026-10-23

Updated installer/p9b_scheduled_combined_lab.ps1 to run four existing genuine NSIS isolated crash/replay tests alongside the three previous independent combined tests under a temporary Windows Scheduled Task. The task verifies its process ancestry and records seven completed tests before cleanup. A longer bounded wait matches actual NSIS compilation and process restart tests. An invalid result is refused with a short failure log tail, and the task remains disposable.

Updated tests/test_rag_p9b_detached_combined_recovery_lab.py so child process paths derive from __file__, not the scheduled worker current working directory. Updated schedule contract tests to require the additional tests and explicit isolated NSIS evidence.

Observed actual scheduled task result: SCHEDULED_COMBINED_LAB_VERIFIED, tests=7, ancestry_verified=true, production_modified=false. All temporary scope only with remapped real Windows HKCU and disposable files/shortcuts.
The scheduled wrapper itself does not install production NSIS; child lab tests do execute genuine lab-built NSIS. This is not a durable autonomous production updater transaction.
Remaining gate: immutable transaction identity, independent restart when updater and supervisor are interrupted, full postverify and operator-approved production cutover.