# RAG-DEL-01.04 DQ-E-D-3C-G-22 — Real scratch worker V2 stdio receipt HMAC

The real isolated_project_worker --pinned-mac-scratch entrypoint (never normal semantic inference) now authenticates the three child-side Win32 stdio descriptor SHA256 receipts along with request/session challenge, project, generation, PID and Win32 birth FILETIME. The parent first independently observes native security descriptors and rejects known broad ACEs, then compares all three signed child receipts to the matching parent pipe ends. A mismatched parent-side descriptor causes fail-closed abort with child reaped and streams closed.

Five additional tests PASS including real Win32 subprocess, synthetic child compatibility, parent-side digest tampering, unknown private namespace and repeated non-authorizing session proofs. No secret is sent via command-line/env/file. The transcript is scratch-only V2; previous V1 test contracts remain for pure unit coverage.

An equal descriptor digest does NOT prove the same kernel object, inherited handle exclusivity, ACL effective permissions, or trusted production endpoint. secure_handle_acl_attested/os_process_identity_attested/activation_authorized stay false. No operational RAG indexing or deletion, no Stable/GitHub changes and no live GUI/MCP mutation.
