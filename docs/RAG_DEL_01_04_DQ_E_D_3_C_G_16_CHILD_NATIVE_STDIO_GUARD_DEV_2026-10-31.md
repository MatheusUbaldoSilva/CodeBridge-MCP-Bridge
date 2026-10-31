# RAG-DEL-01.04 DQ-E-D-3C-G-16 — Native child std-handle type guard (DEV scratch)

Added read-only GetStdHandle / GetFileType checks inside the synthetic MAC child, which is also the handler for the real isolated_project_worker --pinned-mac-scratch mode. The child now refuses the scratch handshake unless stdin, stdout and stderr are native Win32 pipe handles. No model or registered-project resolver is reached.

Five focused tests PASS: all-pipe mocked handles, missing handle, non-pipe handle, real worker pipe roundtrip, and real worker with stdout redirected to NUL rejected. Previously selected 16 G-5/G-9/G-10 regression tests also PASS after the change.

This is not Win32 handle security descriptor access-control verification, and cannot replace OS process/channel authentication. It does not authenticate child inherited handles or grant deletion. Production worker's normal semantic path remains unchanged. Stable, real queue, installed GUI/MCP, Qdrant and GitHub remain untouched.
