# CodeBridge V1.03-D-C — full Python runtime snapshot contract

Status: IMPLEMENTED IN REPOSITORY / NO LIVE SNAPSHOT EXECUTED
Date: 2026-10-20

## Full runtime snapshot

installer/runtime_full_snapshot.py provides a separate full-Python-runtime ZIP.
Default behavior is DRY RUN without copying any live files.
Only an explicit allow_offline_snapshot=True creates an archive outside the installed directory.
It records SHA256 and byte count for every archived file, includes a verification manifest and has a read-only integrity verifier.
The scope is ONLY runtime/python; no credentials, user settings, public RAG storage or installation-wide rollback is promised. Administrators must treat generated runtime archives as potentially sensitive because installed Python directories may contain locally configured package files.
No automatic update, restore, process stop or public index change is implemented.

## Difference from metadata archive

runtime_recovery_archive.py is a METADATA_ONLY recovery record, not sufficient for full runtime rollback.
runtime_full_snapshot.py captures the complete runtime/python directory but still does NOT restore the entire CodeBridge installation. Executable/GUI source and installer versions also need a separately confirmed recovery plan.
Neither tool proves that a live runtime can be restored while CodeBridge is open.

## Gating

The maintenance remains BLOCKED until CodeBridge can be closed safely with an independent recovery channel, operator authorization, verified source installer and a proved rollback rehearsal.
The new snapshot code was only run using temporary synthetic fixtures.
No archive has been created from installed CodeBridge.

## Tests

Offline snapshot synthetic fixtures: dry-run default, archive SHA verification, inside-installation destination rejection and corrupted ZIP rejection.
