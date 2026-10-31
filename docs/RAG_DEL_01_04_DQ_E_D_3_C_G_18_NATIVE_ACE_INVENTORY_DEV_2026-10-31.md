# RAG-DEL-01.04 DQ-E-D-3C-G-18 — Win32 ACE inventory read-only (DEV)

Added a bounded, native Win32 GetAclInformation/GetAce/GetSecurityInfo inspection of the existing anonymous-pipe handle DACL. It inventories basic allow/deny ACE types, access masks and hashed SID identities; detects well-known broad allow trustees (Everyone, Authenticated Users, Builtin Users, Anonymous Logon, Network) and flags any unsupported ACE types. It never writes or replaces the ACL, leaks raw SID/SDDL, or creates a privileged token.

Observation 2026-10-31: newly created test pipe has three simple ALLOW ACEs with owner/identity encoded as SHA256 only; no well-known broad SID detected. Their actual effective access is NOT attested. Absence of a known broad ACE is NOT proof of privacy because other identities, groups, privileges, deny-order precedence, inherited handle copies, and remote access are not evaluated. Result never sets private_acl_attested, effective_access_attested, child_handle_inheritance_attested, activation_authorized or operational_use_allowed.

10 synthetic/Win32 runtime unit tests PASS, including null DACL, failure, closed fd, SID categories and no mutation of file descriptor inheritance. No installed GUI/MCP, Stable, real queue/index or GitHub change. G-19 may introduce a conservative risk gate but must not infer production security.
