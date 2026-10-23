# P9-B real isolated NSIS and recoverer hard-crash replay
Date: 2026-10-23
Status: lab proof PASS; production cutover NOT approved

A common test helper now runs a genuine NSIS executable compiled for one disposable installation directory and deliberately interrupts it after writing 22 new targets and overwriting an original. The new test then:
- Starts a separate detached combined recovery subprocess with P9B_LAB_FAULT_AFTER_SHELL=1.
- Observes the actual hard process exit code 88 before successful journal completion.
- Verifies the interrupted journal has no terminal success attestation.
- Starts a fresh recovery subprocess with the same on-disk journal.
- Requires 236 prior files restored, 22 new targets removed, 5 shortcuts and 2 isolated Windows HKCU key fixtures restored, final journal verified.
- Preserves the earlier non-crash NSIS isolated regression.

This tests real Windows NSIS plus recoverer hard-crash and durable replay in the SAME isolated scenario, not the production CodeBridge installer nor live update.
P9-B remains OPEN because actual official NSIS cutover, independently scheduled supervisor, operator permission and public CBMCP/1 reconnect are not certified.