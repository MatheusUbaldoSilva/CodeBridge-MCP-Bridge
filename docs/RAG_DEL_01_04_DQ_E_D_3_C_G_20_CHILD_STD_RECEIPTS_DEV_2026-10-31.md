# RAG-DEL-01.04 DQ-E-D-3C-G-20 — Child native std-handle SDDL receipts (DEV)

Implemented a scratch-only subprocess which inspects its OWN Win32 GetStdHandle objects for stdin, stdout and stderr using GetSecurityInfo and GetHandleInformation, returning only SHA256 digests of security-descriptor SDDL, pipe-type checks and inheritance flags. This does not use GetFileType alone as proof of kernel identity; it observes ACL descriptors from inside the child.

Five real Windows subprocess tests PASS. All three descriptors matched the corresponding three parent-side anonymous-pipe descriptor digests. The three child handles were marked inheritable, while the parent-side handles were non-inheritable, consistent with Windows subprocess stdio setup. The child failed closed when stdout was redirected to NUL. No raw SID/SDDL is emitted.

Important: an identical security descriptor does NOT uniquely identify the same pipe object, nor does it establish restricted ACL permissions, child process identity or absence of additional handle inheritance. The child is a dedicated lab entrypoint without RAG/models/project data; every operational authorization flag remains false. No Stable, installed GUI/MCP, real queue/index, or GitHub changes.
