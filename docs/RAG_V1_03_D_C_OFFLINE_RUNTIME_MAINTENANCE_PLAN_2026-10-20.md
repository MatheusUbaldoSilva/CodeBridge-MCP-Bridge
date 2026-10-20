# V1.03-D-C — Offline runtime update and rollback plan

Status: PREPARED, NOT EXECUTED
Baseline: Git commit 5f23280
Active installed CodeBridge: 2.0.11-prealpha, still serving MCP

## Preconditions

1. Confirm the active CodeBridge MCP is reachable and save the current checkpoint.
2. Confirm the public RAG generation remains legacy and READY; record document and chunk counts.
3. Verify no pending installer or staged code is about to change the public RAG root.
4. Run bootstrap.ps1 -AuditOnly and capture its structured missing-module list.
5. Verify the isolated staging contract with qdrant-client==1.19.1 and a real Jina offline worker synthetic fixture.
6. Confirm that installed updater refuses changes while CodeBridge is open.
7. Obtain explicit operator approval for a separate maintenance window when this MCP connection can be lost safely.

## Controlled maintenance (not authorized by this document)

1. Save a recovery bundle OUTSIDE the installed directory, including the embedded python313._pth, current requirements, version metadata and installer hash.
2. Check SHA-256 of each saved item before changing the installation.
3. Close CodeBridge by the normal UI only after operator approval and an independent recovery channel exists.
4. Use the official update/bootstrap flow to deploy the packaged RAG sources, Python root import path and pinned dependency versions.
5. Validate the installed interpreter WITHOUT sys.path injection; require qdrant_client, rag runtime, and existing GUI/MCP dependencies.
6. Run a synthetic isolated one-shot real Jina Code staging job using the installed interpreter with both feature flags explicitly set only for that synthetic job.
7. Confirm that the staged receipt is persistent, that the worker returns to OFF and the public index remains unchanged.
8. Restart CodeBridge and confirm READY handshake, MCP terminals and public RAG status.

## Rollback trigger and mechanism

Any package conflict, import failure, MCP handshake failure, index difference, model mismatch, or unstaged file change blocks release.
Do not retry uncontrolled pip updates in a live installation.
If setup fails and CodeBridge is already closed, restore the last verified installer/runtime bundle in a separate controlled session and rerun read-only health checks.
Never roll back the public RAG generation as part of this runtime-only maintenance.
Do not delete or overwrite historical Git dirty paths.

## Go / No-Go

GO only after installed no-injection runtime validation, real offline worker fixture, Git diff+commit audit, SHA evidence, a fresh MCP READY handshake, and confirmation that automatic worker, scheduler and public publication remain OFF.
Until then V1.03-D-C is not deployment-complete.
