# RAG-DEL-01.04 DQ-E-D-3C-G-29 — Read-only child Windows token identity audit (DEV)

Added a scratch-only Win32 OpenProcessToken(TOKEN_QUERY) + GetTokenInformation(TokenUser/TokenIsAppContainer) helper to compare the actual account principal of parent and child using EqualSid. It never returns raw SID, privileges, token handles or owner secrets, and closes queried token handles in all branches. The child must be a caller-supplied held process HANDLE; no processes outside the lab are queried.

Five tests PASS, including a newly spawned short-lived Python child. Results show both parent and child run under the same Windows account SID and the child is not an AppContainer. This is evidence that the scratch worker is NOT running with a distinct principal; it is not a security isolation proof. No token mutations, impersonation, access grants, production IPC validation or real index access.

Effective ACL rights, token restrictions, exclusive handle inheritance and installed GUI provenance remain unverified. Stable, original five dirty files, live RAG indexes/queues, installed GUI/MCP and GitHub unchanged.
