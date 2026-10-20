# PATCH NOTES — CodeBridge V1.03-D-C maintenance preparation

Date: 2026-10-20
State: RUNTIME MAINTENANCE PREPARED / INSTALLED UPDATE NOT EXECUTED
Branch: rag-017-optimized-inference-after-candidate

## Implemented and verified in this session

- Read-only consolidated maintenance preflight reports installed runtime and staged dependency readiness
- Explicit offline maintenance requirement with operator approval and CodeBridge closed
- Read-only SHA-256 fingerprints of embedded Python path, executable, requirements, version, public manifest and SQLite
- Public manifest and SQLite hashes become required preconditions
- Hash comparison rejects any change to public index, allows separately tracked runtime changes
- Installer future payload includes preflight and fingerprint utilities
- Supervised maintenance and rollback plan documented

## Current evidence

- Maintenance candidate only: installed embedded Python lacks root import path, rag and qdrant-client
- Temporarily staged qdrant-client==1.19.1 passed the earlier embedded real Jina worker E2E
- Installer tests: 23 approved
- RAG incremental regression: 284 approved
- Public RAG generation remains legacy and READY
- The installed CodeBridge application and public index have NOT been updated
- Automatic offline worker, watcher, publisher remain disabled
- Two pre-existing unrelated Git dirty items preserved

## Deployment gate still open

Before closing D-C a supervised maintenance window must be explicitly approved
and the installed runtime updated through the official updater with the application closed
and an independent recovery path ready
Then run real Jina worker isolated staging from INSTALLED interpreter without injected paths
Compare public manifest/SQLite fingerprints, re-establish MCP READY and audit Git

No installer was executed and no running CodeBridge service was interrupted
