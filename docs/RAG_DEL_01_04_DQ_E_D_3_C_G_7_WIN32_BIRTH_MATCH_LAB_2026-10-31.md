# RAG-DEL-01.04 DQ-E-D-3C-G-7 — Win32 process creation identity on lab pipe

The MAC scratch parent now compares the process-creation FILETIME reported by the real child with GetProcessTimes applied to the STILL HELD subprocess process HANDLE, in addition to PID and HMAC checks. This prevents a bare numeric PID claim from substituting a different process object in the laboratory. The direct base interpreter bypasses the venv redirector.

G-4/G-5/G-6/G-7 focused tests: 16 PASS. The Win32 birth report is validated using the native handle; it is not itself included in the MAC transcript. The transport remains scratch only and has not been bound to the production worker or protected with explicit Windows ACL audit. Operational deletion, models and Qdrant remain untouched. No Stable or remote GitHub action.
