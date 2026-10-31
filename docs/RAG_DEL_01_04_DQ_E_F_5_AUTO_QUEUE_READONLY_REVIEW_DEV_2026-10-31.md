# RAG-DEL-01.04 DQ-E-F-5 — AUTO queue pending-review metadata (DEV)

Read-only SQLite connection mode=ro, query_only=ON, schema check and maximum 100 nonterminal records. Reports only SHA256 pseudonyms of job and project IDs plus state, existing indexing approval flag, and whether the candidate generation field exists. No private IDs or paths are returned.

Six tests PASS. Real queue observation: one READY_FOR_REVIEW record with approved=true and candidate=true. This is approval for the existing AUTO job workflow, NOT permission for RAG deletion or a generation cutover. No lease or queue barrier is acquired. The inspection returns PENDING_REVIEW_JOBS_PRESENT and activation_authorized=false.

No queue row was changed, no journal reconciled, no index cutover, no Stable or GitHub changes.
