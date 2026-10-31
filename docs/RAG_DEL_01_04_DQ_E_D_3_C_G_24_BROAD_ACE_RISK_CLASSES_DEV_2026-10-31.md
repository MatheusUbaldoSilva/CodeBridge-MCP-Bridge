# RAG-DEL-01.04 DQ-E-D-3C-G-24 — Expand broad-principal denylist (DEV)

Extended the Win32 scratch pipe ACE risk classifier to identify additional potentially broad trustees: INTERACTIVE, SERVICE, BUILTIN_GUESTS, ALL_APPLICATION_PACKAGES, ALL_RESTRICTED_APPLICATION_PACKAGES and REMOTE_DESKTOP_USERS. Their ALLOW ACEs now trigger the G-19 pre-secret-denial behavior in the laboratory. SIDs remain hashed in evidence outputs; categories are deliberately coarse.

The added categories were tested using Win32 ConvertStringSidToSidW to build real valid SID objects, without assigning permissions to any operating-system resource. Focused G-18/G-19/G-22 regression: 22 PASS, zero failures.

This is a denylist expansion, NOT effective-access/ACE-order proof, not a comprehensive SID policy and not a claim of secure production ACLs. Operational authorization and deletion remain blocked. No installed GUI/MCP, Stable, actual indexing data or remote GitHub changes.
