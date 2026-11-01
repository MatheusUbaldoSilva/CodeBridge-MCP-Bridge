# PATCH NOTE — CLOSE-03 actual source Named Pipe scratch transport

Date: 2026-11-01
Branch: dev-local
Status: source transport test only; CLOSE-03 G32 remains blocked.

New tests/test_rag_del_close_03_scratch_named_pipe_transport_dev.py
- Inspects the real source SDDL builder: protected single current-user SID
  grant (GA), medium integrity label, and no broad principal allow.
- Starts the actual NamedPipeServer and NamedPipeClient on a unique,
  disposable channel, verifies framed traffic and two-way close handshake.
- The running disposable kernel Named Pipe DACL is observed natively via Windows GetSecurityInfo; it contains exactly one ALLOW ACE for the current user SID.\r\n- No installed GUI, operational pipe, persistent queue or RAG write occurs.
- Do not confuse same-user pipe authorization with trusted peer identity.

Validation:
- Targeted: 2/2 pass.
- Full RAG-DEL: 784 run, 778 pass, 6 skip, 0 fail.
- RAG-AUTO non-MCP: 241 run, 236 pass, 5 skip, 0 fail.
- MCP-specific tests on preinstalled author_mcp virtualenv: 12 pass.
- Functional acceptance still 40% (CLOSE01/02 only).
