# RAG-DEL-01.04 DQ-E-F-4 — GUI launch process tree observation (DEV)

Read-only process topology observer checks Win32 process records for CodeBridge Launcher -> DEV main.py --no-elevate -> MCP server on 127.0.0.1:8765. Rejects malformed and duplicated PIDs, bad lineage, wrong code root and missing no-elevate marker. Never claims loaded Python modules or GUI RAG reader attestation.

Real Windows observation: 1 launcher candidate, 2 GUI candidates (venv redirector), 2 MCP server candidates (venv redirector), expected ancestry observed. Seven scratch tests PASS. The running GUI has NOT provided direct in-process attestation of the loaded pinned reader. That gate stays FALSE, as do operational authorization flags.

No GUI source modification, service restart, stable edit, queue change or GitHub push.
