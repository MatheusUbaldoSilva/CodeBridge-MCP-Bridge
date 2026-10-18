"""Verified offline fixture restoration without activation or production access."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import tempfile

from rag.runtime.generation_process_lock import generation_lock, GenerationBusy
from rag.runtime.incremental_bundle_validate import validate_incremental_bundle
from rag.runtime.offline_fixture_snapshot import _root, _hash_tree, _redirected, OfflineFixtureError, _qdrant_sqlite_sidecars


class OfflineFixtureRestoreError(RuntimeError):
    pass


def restore_fixture_snapshot(test_root, backup_name, restored_name):
    root = _root(test_root)
    for value in (backup_name, restored_name):
        if not isinstance(value, str) or not value.isidentifier():
            raise OfflineFixtureRestoreError("invalid fixture identity")
    try:
        with generation_lock(root, "offline_capture", exclusive=True):
            return _restore_locked(root, backup_name, restored_name)
    except GenerationBusy as exc:
        raise OfflineFixtureRestoreError("fixture restoration busy") from exc


def _restore_locked(root, backup_name, restored_name):
    backup = root / "offline-fixture-backups" / backup_name
    payload = backup / "snapshot"
    metadata = backup / "report.json"
    destination_parent = root / "offline-fixture-restores"
    destination = destination_parent / restored_name
    for path in (backup.parent, backup, payload, metadata,
                 destination_parent, destination):
        if any(_redirected(part) for part in (path, *path.parents)):
            raise OfflineFixtureRestoreError("redirected path forbidden")
    if any((payload / ("rag_index.sqlite3" + suffix)).exists()
           for suffix in ("-wal", "-shm", "-journal")):
        raise OfflineFixtureRestoreError("unexpected SQLite sidecar")
    if _qdrant_sqlite_sidecars(payload / "qdrant"):
        raise OfflineFixtureRestoreError("Qdrant SQLite sidecar blocks restore")
    if destination.exists() or not metadata.is_file() or not payload.is_dir():
        raise OfflineFixtureRestoreError("missing snapshot or existing target")
    try:
        report = json.loads(metadata.read_text(encoding="utf-8"))
        if report["state"] != "LAB_FIXTURE_SNAPSHOT_ONLY" or report["production_authorized"] is not False:
            raise OfflineFixtureRestoreError("unsafe report state")
        if report["hashes"] != _hash_tree(payload):
            raise OfflineFixtureRestoreError("snapshot fingerprint mismatch")
        verification = validate_incremental_bundle(payload)
        if verification != report["verification"]:
            raise OfflineFixtureRestoreError("snapshot verification mismatch")
    except (KeyError, TypeError, ValueError, OSError, OfflineFixtureError) as exc:
        raise OfflineFixtureRestoreError("invalid backup metadata") from exc
    destination_parent.mkdir(exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".restore-fixture-", dir=destination_parent))
    try:
        copy = staging / "snapshot"
        shutil.copytree(payload, copy)
        if _hash_tree(copy) != report["hashes"]:
            raise OfflineFixtureRestoreError("restored fingerprint mismatch")
        if validate_incremental_bundle(copy) != verification:
            raise OfflineFixtureRestoreError("restored cross-store mismatch")
        if _qdrant_sqlite_sidecars(payload / "qdrant") or _qdrant_sqlite_sidecars(copy / "qdrant"):
            raise OfflineFixtureRestoreError("Qdrant sidecar appeared before restore publication")
        if any((payload / ("rag_index.sqlite3" + suffix)).exists() or (copy / ("rag_index.sqlite3" + suffix)).exists() for suffix in ("-wal", "-shm", "-journal")):
            raise OfflineFixtureRestoreError("SQLite sidecar appeared before restore publication")
        if _hash_tree(payload) != report["hashes"]:
            raise OfflineFixtureRestoreError("snapshot changed before restore publication")
        if _hash_tree(copy) != report["hashes"]:
            raise OfflineFixtureRestoreError("restored copy changed before publication")
        if destination.exists():
            raise OfflineFixtureRestoreError("destination appeared during restore")
        os.rename(staging, destination)
        return {"state": "LAB_FIXTURE_RESTORED_NOT_ACTIVATED",
                "backup": backup_name, "target": restored_name,
                "verification": verification, "production_authorized": False}
    finally:
        if staging.exists():
            shutil.rmtree(staging)
