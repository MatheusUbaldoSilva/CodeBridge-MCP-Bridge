# P9-B ? Independent scheduled real-snapshot recovery in disposable lab

Date: 2026-10-23
Result: SCHEDULED_SNAPSHOT_DISPOSABLE_RECOVERY_VERIFIED
State: LAB ONLY; P9-B REMAINS OPEN.

## Evidence

A transient Windows Scheduled Task named
CodeBridge_P9B_Snapshot_Disposable_Lab ran the test in an external
Python process, with process ancestry checked by the project's
inspect_detached_process_ancestry guard.

The real preinstall file snapshot was an input:
P9B_FILE_ROLLBACK_b3e5e5e42e5f.zip
(bound to the isolated candidate from source commit
b3e5e5e42e5f3650f8fed6824f15da1ddf1939ff).
No installation or NSIS execution occurred.

Within a Python TemporaryDirectory the worker:
- Verified backup scope of 258 targets and 236 existing files
- Prepared an isolated installation from all 236 actual backed-up files
- Spawned a child that interrupted itself with exit code 83
- Spawned a different process that recovered with exit code 0
- Verified 236 old files recovered and 22 new targets removed
- Verified 5 shortcut fixtures and 2 fake registry-key fixtures
- Returned ancestry_verified=true, verified=true,
  production_modified=false and nsis_executed=false

The scheduled task was unregistered; both scheduled-worker folders
and temporary E2E installation folders were verified absent.

## Boundaries

The registry in this test was simulated and all writes were inside
a disposable directory. This proves that a Windows task with
independent ancestry can perform this full snapshot-backed lab
without the CodeBridge MCP being its process parent.

It does NOT certify a production-grade mutating supervisor,
real HKCU recovery after a cutover, durable restart policy,
an actual NSIS interruption, or CBMCP/1 restart handshake.

Next: certify an independent transaction runner on an isolated
real installation with recovery journal replay. Then require an
operator-approved production window, fresh backups and post-update
MCP/queue/RAG proof before P9-B closure.
