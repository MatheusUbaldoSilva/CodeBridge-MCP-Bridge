# P9-B isolated NSIS payload / rollback scope parity

Date: 2026-10-23
Status: READ-ONLY PAYLOAD INVENTORY PASS / NOT PRODUCTION CUTOVER

Candidate installer CodeBridge-Setup.exe in
LOCALAPPDATA/CodeBridge-MCP-Bridge/release_staging/
P9B_SOURCE_ONLY_b3e5e5e42e5f_TREE/installer/dist/
SHA256 B9A6409E809D495D76AB8BFFEDA1BB94A41563539002090F6AFAC20C89FB0C2B

The candidate file table was read with 7-Zip listing mode (-slt);
the executable was NOT run or extracted into the installed application.
After normalizing Windows path separators, its file table was
compared against targets in P9B_FILE_ROLLBACK_b3e5e5e42e5f.zip.

Result:
- 7z inventory command: exit 0
- 258 rollback targets inspected
- 258 targets appear in candidate NSIS inventory
- 0 rollback targets missing from candidate NSIS inventory
- 6 additional NSIS entries consist of internal $PLUGINSDIR
  resources and the top-level setup archive record

This proves inventory parity only; it does not prove safe execution,
file contents after installation, rollback correctness or postupdate
CBMCP/1 connection. P9-B remains OPEN. Existing 236 file preimage,
22 absent-new-target markers, 5 shortcuts and 2 HKCU keys must still
be fresh-checked at a future operator-approved maintenance cutover.
No live NSIS installation, public RAG mutation or MCP shutdown occurred.
