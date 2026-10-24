# P9-B — Bounded retry adapter exercises actual detached combined recovery in disposable Windows lab
Date: 2026-10-24
State: real isolated HKCU+files rollback PASS; genuine NSIS install/update and independent scheduler crash restoration NOT YET CERTIFIED. P9-B OPEN.

New tests/test_rag_p9b_scheduled_combined_retry_real_hkcu.py reuses the existing FullScopeActualHKCUTests fixture and existing detached_combined_recovery_lab.execute() rather than rebuilding rollback. The official pre-install file snapshot in CodeBridge release_staging is copied to a fresh Windows TEMP scratch area with the SHA-256 verified before the bounded adapter consumes it; its hash is unchanged. Shell snapshot, preimage, desktop, appdata and real two remapped HKCU keys remain inside isolated fixture TEMP.

Integration proof: existing recovery report COMBINED_LAB_RECOVERY_VERIFIED, 236 old files, 22 newly created targets removed, five shortcuts, two isolated real HKCU keys, final shell verification. Durable retry ledger enters TERMINAL after verified restore. A second adapter invocation returns DURABLE_TERMINAL_STATE and does not reinvoke the worker. No official installed CodeBridge or public HKCU changed.

The full P9B regression passed 593 tests in 60.540 seconds on re-run. First full suite attempt had an intermittent two-process retry reservation failure (a process returned no 'attempt'); isolated two-process test passed eight consecutive runs afterward. Keep concurrency stress investigation OPEN; do not claim the first run clean. This shows actual isolated rollback through the adapter using an in-process worker, NOT independently periodically restarted genuine NSIS cutover.

Remaining: authenticated root, frozen transaction identity, actual single crash-durable journal spanning installer/files/shell, periodic scheduled hard supervisor-death proof, and explicit production operator authorization.