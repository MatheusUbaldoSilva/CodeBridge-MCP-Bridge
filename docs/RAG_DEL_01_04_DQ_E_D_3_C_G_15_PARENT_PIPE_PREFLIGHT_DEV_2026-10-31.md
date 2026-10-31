# RAG-DEL-01.04 DQ-E-D-3C-G-15 — Scratch-pipe preflight before secret (DEV)

The bounded scratch MAC parent now checks all three of its Win32 stdin/stdout/stderr pipe handles immediately after Popen and before writing a secret. Requires successful GetSecurityInfo owner and non-null DACL observations and GetHandleInformation showing all three parent-side handles non-inheritable. Failure aborts before sending secret; finally kills and reaps the child and closes all three parent streams. Neither an ACL change nor a new Windows privilege is requested.

Five G-15 tests PASS, including rejection of absent/missing DACL and unexpectedly inheritable handles, each with process reaping confirmation. Repeated with timeout tests under python -W error::ResourceWarning: 8 PASS with zero warnings after fixing early-abort stream closure. Real scratch worker and synthetic worker pass. No installed GUI/MCP change.

IMPORTANT: This preflight does not prove that the DACL lacks broad ACEs, that the child inherited only intended std handles, or that the child has a secure production principal. secure_handle_acl_attested remains false; deletion stays blocked.
