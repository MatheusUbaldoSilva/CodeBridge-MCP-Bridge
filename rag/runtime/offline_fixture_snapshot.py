"""Offline fixture-only snapshot. Not authorized for production use."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile

from rag.runtime.incremental_bundle_validate import validate_incremental_bundle
from rag.runtime.generation_process_lock import generation_lock, GenerationBusy
from rag.runtime.offline_fixture_file_guard import hold_fixture_files_readonly, FixtureFileBusy


class OfflineFixtureError(RuntimeError):
    pass


def _redirected(path):
    path = Path(path)
    return path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction())


def _root(path):
    original = Path(path)
    if any(_redirected(part) for part in (original, *original.parents)):
        raise OfflineFixtureError("symlink root forbidden")
    root = original.resolve(strict=True)
    if root.name.casefold() != "codebridge-rag-generation-test":
        raise OfflineFixtureError("fixture root required")
    return root


def _hash_tree(root):
    hashes = {}
    for path in sorted(root.rglob("*")):
        if _redirected(path) or (path.is_file() and path.stat().st_nlink > 1):
            raise OfflineFixtureError("redirected or hardlinked file forbidden")
        if path.is_file():
            hashes[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def _qdrant_sqlite_sidecars(tree):
    for path in Path(tree).rglob("*"):
        name = path.name.lower()
        for suffix in ("-wal", "-shm", "-journal"):
            if name.endswith(suffix) and name[:-len(suffix)].endswith((".sqlite", ".sqlite3", ".db")):
                return True
    return False


def capture_fixture(source_root, backup_name):
    root = _root(source_root)
    try:
        with generation_lock(root, "offline_capture", exclusive=True):
            return _capture_locked(root, backup_name)
    except (GenerationBusy, FixtureFileBusy, shutil.Error, PermissionError) as exc:
        raise OfflineFixtureError("fixture capture blocked by another process") from exc


def _capture_locked(root, backup_name):
    files = [root / "rag_index.sqlite3", root / "rag-index-manifest.json"]
    files += [file for file in (root / "qdrant").rglob("*") if file.is_file()]
    with hold_fixture_files_readonly(files):
        return _capture_guarded(root, backup_name)


def _capture_guarded(root, backup_name):
    """Capture only a closed synthetic fixture into a new local backup directory."""
    if not isinstance(backup_name, str) or not backup_name.isidentifier():
        raise OfflineFixtureError("invalid backup name")
    for name in ("rag_index.sqlite3", "rag-index-manifest.json", "qdrant"):
        path = root / name
        if not path.exists() or _redirected(path) or (path.is_file() and path.stat().st_nlink > 1):
            raise OfflineFixtureError("incomplete or redirected fixture")
    db = root / "rag_index.sqlite3"
    for suffix in ("-wal", "-shm", "-journal"):
        if (root / (db.name + suffix)).exists():
            raise OfflineFixtureError("SQLite sidecar blocks capture")
    backups = root / "offline-fixture-backups"
    target = backups / backup_name
    if _redirected(backups) or target.exists() or _redirected(target):
        raise OfflineFixtureError("existing or redirected backup forbidden")
    if _qdrant_sqlite_sidecars(root / "qdrant"):
        raise OfflineFixtureError("Qdrant SQLite sidecar blocks capture")
    before = _hash_tree(root / "qdrant")
    db_hash = hashlib.sha256(db.read_bytes()).hexdigest()
    manifest_hash = hashlib.sha256((root / "rag-index-manifest.json").read_bytes()).hexdigest()
    backups.mkdir(exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".fixture-", dir=backups))
    try:
        payload = stage / "snapshot"
        payload.mkdir()
        shutil.copy2(db, payload / db.name)
        shutil.copy2(root / "rag-index-manifest.json", payload / "rag-index-manifest.json")
        shutil.copytree(root / "qdrant", payload / "qdrant")
        if _hash_tree(payload / "qdrant") != before:
            raise OfflineFixtureError("vector files changed during copy")
        if hashlib.sha256((payload / db.name).read_bytes()).hexdigest() != db_hash:
            raise OfflineFixtureError("SQLite changed during copy")
        if hashlib.sha256((payload / "rag-index-manifest.json").read_bytes()).hexdigest() != manifest_hash:
            raise OfflineFixtureError("manifest changed during copy")
        # Validate copied SQLite without mutating the source.
        conn = sqlite3.connect((payload / db.name).as_uri() + "?mode=ro", uri=True)
        try:
            if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise OfflineFixtureError("SQLite integrity failed")
        finally:
            conn.close()
        if (_hash_tree(root / "qdrant") != before or
                hashlib.sha256(db.read_bytes()).hexdigest() != db_hash or
                hashlib.sha256((root / "rag-index-manifest.json").read_bytes()).hexdigest() != manifest_hash):
            raise OfflineFixtureError("source changed during capture")
        try:
            verified = validate_incremental_bundle(payload)
        except Exception as exc:
            raise OfflineFixtureError("cross-store verification failed") from exc
        report = {"state": "LAB_FIXTURE_SNAPSHOT_ONLY", "verification": verified,
                  "hashes": _hash_tree(payload),
                  "production_authorized": False, "active_generation_changed": False}
        (stage / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        if _qdrant_sqlite_sidecars(root / "qdrant") or _qdrant_sqlite_sidecars(payload / "qdrant"):
            raise OfflineFixtureError("Qdrant SQLite sidecar appeared before publication")
        if any((root / (db.name + suffix)).exists() for suffix in ("-wal", "-shm", "-journal")):
            raise OfflineFixtureError("SQLite sidecar appeared before publication")
        if (_hash_tree(root / "qdrant") != before or
                hashlib.sha256(db.read_bytes()).hexdigest() != db_hash or
                hashlib.sha256((root / "rag-index-manifest.json").read_bytes()).hexdigest() != manifest_hash):
            raise OfflineFixtureError("source changed before snapshot publication")
        if _hash_tree(payload) != report["hashes"]:
            raise OfflineFixtureError("staging changed before snapshot publication")
        if target.exists() or target.is_symlink():
            raise OfflineFixtureError("concurrent destination")
        os.rename(stage, target)
        return report
    finally:
        if stage.exists():
            shutil.rmtree(stage)
