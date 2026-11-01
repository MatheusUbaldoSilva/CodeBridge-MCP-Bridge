# CLOSE-03 — Kernel peer token and loaded source matching on installed DEV GUI witness

Date: 2026-11-01. Read-only DEV diagnostic, never operational deletion.

The active GUI witness now independently obtains GetNamedPipeClientProcessId,
reads the actual connected witness pipe kernel OWNER/GROUP/DACL and runs
AccessCheck on the client's actual process token for FILE_READ_DATA. If the
client-token check is missing/denied, no witness reply is emitted.

The external verifier pins actual OS GUI server PID and process creation time
before reading; checks the one-time random challenge, server PID, claimed
client PID against current verifier process, effective token AccessCheck,
loaded method hashes and loaded module paths against freshly loaded DEV source.
Any mismatch blocks the observer; the only successful status is
GUI_LOADED_CODE_KERNEL_PINNED_READONLY.

These checks concern the newly introduced diagnostic GUI witness pipe, NOT
the existing PowerShell terminal IPC, and NOT a dedicated RAG deletion command
transport (which has not been wired). No code is permitted to turn on deletion,
approve queue jobs, rollback the RAG-AUTO canary, or publish generations.

Validation: two targeted independent-process GUI tests PASS and whole RAG-DEL
regression 796 run, 790 PASS, 6 SKIP, 0 failures.
The installed running GUI must be restarted to load the updated witness code.
G32 stays blocked pending explicit operational authorization and the
newworldpvp READY_FOR_REVIEW / CANARY_ACTIVE state reconciliation.
