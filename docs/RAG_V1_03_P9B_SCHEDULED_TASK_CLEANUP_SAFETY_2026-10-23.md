# P9-B - Task cleanup safety
Date: 2026-10-23
State: isolated lab verified; P9-B remains OPEN

The disposable Windows Scheduled Task supervisor now checks whether its own task is still running during final cleanup. If so it requests Stop-ScheduledTask for that specific temporary task, waits for a bounded state transition, and refuses file cleanup if that task remains Running. This avoids deleting worker source while a task is still using it after timeout, without killing installed CodeBridge or global processes.
No task in production is stopped, no live installation or RAG index is changed.

Verification: two static/PowerShell parse tests PASS; actual independently scheduled Windows lab SCHEDULED_COMBINED_LAB_VERIFIED with seven genuine isolated NSIS/rollback integration tests, ancestry verified and production_modified false.

Outstanding: durable recovery across parent and child restarts with independent transaction trust roots, and explicit operator-authorized production NSIS update.