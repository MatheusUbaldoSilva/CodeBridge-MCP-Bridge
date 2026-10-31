# RAG-DEL-01.04 DQ-E-D-3C-G-25 — Native Win32 same-end handle comparison lab

A read-only DEV helper imports an already-existing remote handle into the caller's process using DuplicateHandle(DUPLICATE_SAME_ACCESS) and compares it to a caller-held same-end pipe handle using kernelbase.CompareObjectHandles. Any imported temporary handle is closed in finally. It returns fail-closed status on invalid parent descriptors, remote handles, wrong object type or mismatching kernel objects. It neither creates access grants nor changes DACL or inheritance.

Seven tests PASS against current-process duplicate-handle proxies, including exact match, os.dup same-end match, opposite pipe-end mismatch, invalid native handles, closed file descriptor and false operational flags. This phase does NOT yet exercise a real separate child; this is a low-level primitive for the next phase.

Limitations: DuplicateHandle and identity matching do not attest process binary, birth, token, exclusive channel, effective ACL, or production RAG. A separate bounded child lab with real process-handle proof is required. No Stable or live GUI/MCP, queue, index, GitHub push changes.
