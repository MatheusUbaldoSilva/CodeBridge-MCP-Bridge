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


class OfflineFixtureError(RuntimeError):
    pass


def _root(path):
    original = Path(path)
    if original.is_symlink():
        raise OfflineFixtureError("symlink root forbidden")
    root = original.resolve(strict=True)
    if root.name.casefold() != "codebridge-rag-generation-test":
        raise OfflineFixtureError("fixture root required")
    return root


def _hash_tree(root):
    hashes = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise OfflineFixtureError("symlink forbidden")
        if path.is_file():
            hashes[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def capture_fixture(source_root, backup_name):
    """Capture only a closed synthetic fixture into a new local backup directory."""
    root = _root(source_root)
    if not isinstance(backup_name, str) or not backup_name.isidentifier():
        raise OfflineFixtureError("invalid backup name")
    for name in ("rag_index.sqlite3", "rag-index-manifest.json", "qdrant"):
        path = root / name
        if not path.exists() or path.is_symlink():
            raise OfflineFixtureError("incomplete or redirected fixture")
    db = root / "rag_index.sqlite3"
    for suffix in ("-wal", "-shm", "-journal"):
        if (root / (db.name + suffix)).exists():
            raise OfflineFixtureError("SQLite sidecar blocks capture")
    backups = root / "offline-fixture-backups"
    target = backups / backup_name
    if backups.is_symlink() or target.exists() or target.is_symlink():
        raise OfflineFixtureError("existing or redirected backup forbidden")
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
        if target.exists() or target.is_symlink():
            raise OfflineFixtureError("concurrent destination")
        os.rename(stage, target)
        return report
    finally:
        if stage.exists():
            shutil.rmtree(stage)
