# CodeBridge RAG V1.03-D-C - Offline Worker Contract

State: PLANNED, NOT ACTIVATED. Depends on D-A source prequeue gate and D-B durable queue, commit a7500e1.

## D-C-A - Independent consumer

- An application-managed process outside the MCP may consume jobs only after an explicit operator enablement. Default OFF.
- Read the dedicated jobs/incremental_jobs.sqlite3 database; never open the active Qdrant as a writer, touch rag_index.sqlite3 or write a generation pointer.
- Revalidate committed source Git HEAD, canonical SHA-256, individual approved source path and indexing denylist at reservation time and again before recording success.
- Lease token must expire and be refreshed explicitly; stale workers must not acknowledge another worker's reservation.

## D-C-B - Offline indexing

- Create a unique isolated staging/build-* directory via existing Jina and build_staged_index.
- Verify staged SQLite, manifest, document path and SHA, appropriate model, vector IDs and counts with validate_incremental_bundle.
- Acknowledge only from a current unexpired lease, after post-index SHA verification and durable receipt. Use SQLite compare-and-swap for the terminal STAGED_OFFLINE_VALIDATED state.
- Stage completion never authorizes publication or modification of the public MCP index.

## D-C-C - Recovery

- Cover PENDING, CLAIMED, RETRY, REJECTED, FAILED, STAGED_OFFLINE_VALIDATED with bounded retry, lease expiry, revalidation after restart and progress visibility.
- Test two independent worker processes on Windows sharing one queue without duplicate execution, and safe recovery after crash.
- No automatic cleanup of prior staging or immutable generations without a separate audit.

## D-C-D - Production safety

- Worker settings and scheduling remain OFF until end-to-end tests, source approvals, explicit operator enablement and rollback evidence are complete.
- Keep source content and lease tokens out of status responses.
- Permanent index activation always needs a separate permission and supervised generation switch. The earlier single-use V1.03-C reversible trial has already been consumed.

Current status: D-B persists and reserves work; there is NO active scheduler, embeddings worker, completion acknowledgment or automatic publishing. D-C remains open.
