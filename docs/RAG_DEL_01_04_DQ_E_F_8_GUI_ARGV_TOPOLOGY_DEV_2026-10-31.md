# RAG-DEL 01.04 DQ-E-F-8 — Strict Windows GUI process argv topology (DEV)

Fixed F-4 raw command-line substring matching. A process invoking Python with -c and a GUI path embedded as text could previously look like a real GUI. The new Win32 CommandLineToArgvW parser extracts exact argv tokens, requires python/pythonw executable and exact script path in argv[1], exact GUI --no-elevate flag and MCP --port 8765 pair. Confirms launcher -> GUI -> MCP parent/child lineage. No raw command line is emitted as evidence. Observation-only, no installed process changes.

13 tests PASS including adversarial flags/path injection, python -c impersonation, wrong launcher, wrong interpreter and misplaced port. A real Windows CIM snapshot observed 1 matching launcher, 2 GUI and 2 MCP candidate processes: exact-argv topology positive. Loaded module and trusted installed GUI proof remain FALSE. Runtime deletion remains blocked.

No installed GUI modules inspected, no Stable, original dirty files, live queues/indices, installed GUI/MCP, GitHub changes.
