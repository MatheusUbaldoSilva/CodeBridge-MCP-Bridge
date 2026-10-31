# RAG-DEL-01.04 DQ-E-D-3C-G-6 — Direct Win32 PID correlation (lab)

The scratch parent launches the base Python interpreter using sys._base_executable instead of the venv redirector. It compares child-reported PID to the subprocess PID before trusting the session HMAC. This avoids the previously observed Windows venv redirector mismatch in the laboratory. Exact session challenge and request HMAC remain mandatory.

Sixteen G-4/G-5/G-6 focused tests PASS. This is still not OS object creation-time attestation: the laboratory does NOT yet bind the Win32 process creation FILETIME and handle to the private pipe credential. Production readiness remains false. No real worker or installed MCP/GUI changed.
