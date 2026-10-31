# RAG-DEL-01.04 DQ-E-D-3C-G-12 — Windows marker read race hardening

The Win32 parent-kill regression sometimes observed existence of lab-child-termination.json before the child had finished writing the JSON object. The test failed with JSONDecodeError even though the child eventually wrote the valid terminal state. The test now waits for a parsable state within the same bounded polling window and still requires PARENT_PIPE_CLOSED or PARENT_PROCESS_EXITED. It does not ignore missing/incorrect final states.

Evidence: the previously failing test PASS once, then PASS eight consecutive isolated repeats. This is test synchronization only; it does not mask worker errors, alter the operational process or relax deletion gates. No Stable or GitHub changes.
