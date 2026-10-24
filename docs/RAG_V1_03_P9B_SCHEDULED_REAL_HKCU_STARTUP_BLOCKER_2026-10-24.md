# P9-B.03 — Windows Task Scheduler actual scoped-HKCU adapter boot blocker
Date: 2026-10-24
State: FAILED / NOT CERTIFIED. P9-B remains OPEN.

Attempted a disposable uniquely named Task Scheduler periodic lab invoking the existing durable retry adapter with the actual 236/22 file + 5 shortcut + 2 scoped HKCU fixture. Scheduled task registration succeeded, but a 185-second attempt observed no retry-ledger first reservation: SCHEDULED_INITIAL_ATTEMPT_NOT_OBSERVED. Test execution exited with failure after 192.732 seconds. Since the first worker invocation itself is unproven, there is no claim of automatic rollback recovery.

The scratch task cleanup branch completed, and a separate read-only query found LEFTOVER_SCHEDULED_REAL_TASKS=0. No production installation, official HKCU or RAG was touched. The failed experimental test source was removed from the repository workspace and NOT staged or shipped as a passing test. Last stable test full suite at this point was 602 P9B tests PASS before this separate failed experiment.

Next diagnostic should be SHORT and instrument task startup *before imports* via a persistent TEMP boot marker and captured stdout/stderr, inspect LastRunTime, LastTaskResult, registered XML trigger/repetition, action path, worker cwd/environment and Python import path. Only when initial task execution is observed should a 1-minute repeated recovery test be attempted. Do not enable global TaskScheduler/Operational log or change system settings without approval.

Independent P9-B.01-C protected trust root and P9-B.02-C genuine single NSIS transaction are also missing. No live cutover authorized.