# RAG-DEL-01.04 DQ-E-D-3C-G-31 — Windows token integrity labels (DEV read-only)

Added a bounded scratch-only TokenIntegrityLevel inspection using Win32 GetTokenInformation on caller-held process handles. It parses the RID from the token mandatory-label SID and returns ONLY coarse integrity categories (UNTRUSTED, LOW, MEDIUM, HIGH, SYSTEM or PROTECTED_OR_UNKNOWN). No raw SID, privilege list, token handles, AccessCheck rights or credentials are exposed; queried handles are closed.

Five tests PASS, including a real newly spawned Windows Python child and failure/invalid process handle conditions. On this DEV host, parent and child both report MEDIUM integrity. Equal integrity DOES NOT establish token privilege isolation or effective ACL access. The helper always keeps privilege_isolation_attested, effective_acl_attested, activation_authorized and operational_use_allowed false. Not yet wired to the scratch live MAC handshake; that is G-32.

No modifications to installed GUI, MCP, stable, actual queue, indexes, secrets, or remote GitHub.
