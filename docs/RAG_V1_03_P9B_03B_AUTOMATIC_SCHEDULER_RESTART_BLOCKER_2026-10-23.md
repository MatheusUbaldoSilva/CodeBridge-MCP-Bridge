# P9-B.03-B — Automatic Windows Task Scheduler relaunch blocker
Date: 2026-10-23
Status: BLOCKED / no autonomous restart certification; P9-B OPEN.

Two actual disposable Windows Scheduled Task experiments were executed. Both used isolated Windows TEMP scratch only, task name CodeBridge_P9B_Restart_Scratch_Lab, unprivileged interactive principal, test Python first os._exit(87), and expected scheduler-managed relaunch to produce proof for attempt 2. Configuration 1: task started by Start-ScheduledTask with RestartCount=2 and RestartInterval=1 minute. Configuration 2: initial start delegated to a -Once trigger in the near future with the same restart settings. Neither emitted the automatic-restart success proof before a 160-second bounded timeout; both produced AUTOMATIC_RESTART_TIMEOUT. Do NOT claim automatically restarting worker or P9-B.03 completion.

After each run, finally block unregistered disposable task and removed its scratch folder; independently reaudited:
TASK_REMAINS=False
LAB_FOLDERS_REMAIN=0
Task Scheduler Operational event log enabled: False.

The latter fact limits diagnosis; we did not enable system-wide logging or change production scheduler settings without operator approval. Unknown whether first task failed to start, restart-after-failure policy was not applied, or user-context Task Scheduler restrictions prevented it.

The exploratory disposable script was removed from working tree instead of versioning a test with a known failed runtime proof. Follow-up: read-only inspect Task Scheduler LastTaskResult and task XML during live test before cleanup; preserve failure diagnostics outside the soon-to-be-deleted folder, verify first actual exit 87; test isolated triggering and restart policies separately. Do not manually trigger a second attempt and call it automatic. Do not connect this until gate succeeds and independent artifact trust is proven.

Earlier bounded three-attempt durable retry ledger remains published fd80958 with 563 full P9B tests PASS, and Windows junction hardening b87f515 with 554 tests PASS. These are distinct from the failed automatic restart proof. Production CodeBridge, NSIS, public HKCU, MCP and active RAG remain unchanged.