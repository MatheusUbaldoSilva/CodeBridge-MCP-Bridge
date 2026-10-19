"""Capture an isolated, verified baseline of the real active CodeBridge index.

SQLite online backup is used for each DB; never copy open DB files raw.
The clone is not an activation, nor a simultaneous multi-DB transaction.
Cross-store validation and drift checks are mandatory before consuming it.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
from uuid import uuid4

from rag.runtime.incremental_bundle_validate import validate_incremental_bundle
from rag.runtime.status import resolve_rag_sqlite_path, resolve_rag_manifest_path
from rag.index.qdrant_local import resolve_qdrant_local_path


class ActiveSnapshotError(RuntimeError):
    pass


def _fingerprint(paths):
    return {str(p): (p.stat().st_size, p.stat().st_mtime_ns) for p in paths}


def _backup_sqlite(source: Path, destination: Path):
    uri = source.resolve().as_uri() + "?mode=ro"
    reader = sqlite3.connect(uri, uri=True, timeout=15)
    try:
        reader.execute("PRAGMA query_only=ON")
        writer = sqlite3.connect(destination)
        try:
            reader.backup(writer, pages=1024, sleep=0.05)
            writer.commit()
        finally:
            writer.close()
    finally:
        reader.close()


def capture_active_baseline(*, state_root: Path | None = None) -> dict:
    """Create a new closed recovery baseline in existing RAG staging hierarchy."""
    active_db = resolve_rag_sqlite_path().resolve()
    manifest = resolve_rag_manifest_path().resolve()
    vector_root = resolve_qdrant_local_path().resolve()
    if state_root is None:
        state_root = active_db.parent
    state_root = Path(state_root).resolve()
    if active_db.parent != state_root or manifest.parent != state_root:
        raise ActiveSnapshotError("live index is not in the approved CodeBridge state root")
    if vector_root != state_root / "qdrant":
        raise ActiveSnapshotError("unexpected active Qdrant root")
    files = [
        active_db, manifest, vector_root / "meta.json",
        vector_root / "collection" / "text" / "storage.sqlite",
        vector_root / "collection" / "code" / "storage.sqlite",
    ]
    if any(not p.is_file() for p in files):
        raise ActiveSnapshotError("active index has missing files")
    before = _fingerprint(files)
    manifests_before = {
        str(p): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (manifest, vector_root / "meta.json")
    }
    folder = state_root / "staging" / ("baseline-" + uuid4().hex)
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "qdrant" / "collection" / "text").mkdir(parents=True)
    (folder / "qdrant" / "collection" / "code").mkdir(parents=True)

    # Never delete an incomplete capture automatically. It is an auditable
    # failed artifact, not something that should be promoted to production.
    try:
        _backup_sqlite(active_db, folder / "rag_index.sqlite3")
        shutil.copy2(manifest, folder / "rag-index-manifest.json")
        shutil.copy2(vector_root / "meta.json", folder / "qdrant" / "meta.json")
        for name in ("text", "code"):
            _backup_sqlite(
                vector_root / "collection" / name / "storage.sqlite",
                folder / "qdrant" / "collection" / name / "storage.sqlite",
            )
        if _fingerprint(files) != before:
            raise ActiveSnapshotError("source DB changed during backup")
        after_manifests = {
            str(p): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (manifest, vector_root / "meta.json")
        }
        if after_manifests != manifests_before:
            raise ActiveSnapshotError("manifest or vector schema changed during capture")
        validated = validate_incremental_bundle(folder)
        receipt = {
            "status": "CLOSED_BASELINE_VALIDATED_NOT_PUBLISHED",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_root": str(state_root),
            "snapshot_root": str(folder),
            "source_fingerprint": {key: {"size": size, "mtime_ns": mtime}
                                   for key, (size, mtime) in before.items()},
            "source_hashes": manifests_before,
            "validation": validated,
            "not_a_live_atomic_snapshot": True,
            "activation_permitted": False,
        }
        receipt_path = folder / "baseline-receipt.json"
        receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True),
                                encoding="utf-8")
        return receipt
    except BaseException as exc:
        (folder / "CAPTURE_FAILED.txt").write_text(
            type(exc).__name__ + ": " + str(exc), encoding="utf-8",
        )
        raise