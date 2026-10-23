# P9-B ? Recovery against actual candidate backup in disposable installation

Date: 2026-10-23
State: DISPOSABLE END-TO-END PASS; PRODUCTION CUTOVER NOT AUTHORIZED

## Provenance

Candidate source commit b3e5e5e42e5f3650f8fed6824f15da1ddf1939ff.
Input snapshot: LOCALAPPDATA/CodeBridge-MCP-Bridge/release_staging/
P9B_FILE_ROLLBACK_b3e5e5e42e5f.zip.
Production installation was READ-ONLY input for snapshot verification.
The lab root was created with Python tempfile.TemporaryDirectory
outside the actual installed directory.

## Observed phases

1. installer.rag_p9b_unified_e2e_lab.prepare returned
   UNIFIED_LAB_READY with baseline_files=236.
2. A separate Python process ran the disposable interrupt phase,
   exited with code 83 (intentional process interruption).
3. A subsequent, separate Python process ran the recovery phase,
   exited with code 0, state UNIFIED_LAB_RECOVERED.
4. Recovery checks: old_files_checked=236, new_targets_removed=22,
   shortcuts_checked=5, fake_registry_keys_checked=2,
   production_modified=false, recovered=true.
5. TemporaryDirectory cleanup completed. No Windows scheduled task
   or production NSIS process was involved.

## Limits

The registry in this unified lab was SIMULATED and isolated;
this result is not a real HKCU production rollback.
Although separate subprocesses recovered the data, they were
started by a CodeBridge-controlled test invocation, not a durable
independently scheduled mutating production supervisor.
The actual installed files, RAG public generation, shortcuts and HKCU
were NOT modified.

Next: schedule the same snapshot-backed DISPOSABLE scenario through an
external supervisor and attest external ancestry and cleanup.
Then certify the production-grade independent crash journal,
file/HKCU/shortcut rollback, deliberate stop, and poststart CBMCP/1
handshake before considering any operator-approved NSIS cutover.

P9-B remains OPEN.
