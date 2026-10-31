# RAG-DEL-01.04 DQ-E-D-3C-G-14 — Win32 anonymous-pipe security-descriptor observation (DEV)

Added a read-only Windows GetSecurityInfo kernel-object descriptor observer and GetHandleInformation inheritability inspector. Both operate only on caller-provided already-open file descriptors; they do not create, duplicate, grant or change handles or ACLs. The observer returns owner/DACL presence, a SHA256 digest of the SDDL and whether the local handle is inheritable. No raw SID/SDDL or pipe contents are returned.

On 2026-10-31, both ends of a freshly created local anonymous pipe showed owner and DACL, the same SDDL digest and parent-side handles not inheritable. Seven unit tests PASS, including inheritable-handle detection, invalid/closed descriptor cases.

IMPORTANT: DACL presence and a digest are NOT proof that rights are sufficiently restrictive; no ACE/SID allow-list verification or child inherited-handle inspection has been implemented. private_acl_attested and child_handle_inheritance_attested intentionally remain false. This is an observation-only DEV milestone, no operational authority, no real deletion/model/queue access.
