"""Coordinate three isolated incremental stores; never publish production.

Inputs must be stable, closed snapshots. Result remains staged only.
"""
from pathlib import Path
import shutil

from rag.runtime.incremental_sqlite_stage import stage_incremental_sqlite
from rag.runtime.incremental_manifest_stage import stage_incremental_manifest
from rag.runtime.incremental_qdrant_stage import stage_incremental_qdrant


class IncrementalBundleError(RuntimeError):
    pass


def stage_incremental_bundle(old_root, incoming_root, destination, project_id,
                             *, fail_after=None):
    old, new, output = (Path(p).resolve() for p in
                        (old_root, incoming_root, destination))
    if len({old, new, output}) != 3 or output.exists():
        raise IncrementalBundleError("destination must be new and distinct")
    for folder in (old, new):
        if not folder.is_dir():
            raise IncrementalBundleError("snapshot directory missing")
        for part in ("rag_index.sqlite3", "rag-index-manifest.json", "qdrant"):
            if not (folder / part).exists():
                raise IncrementalBundleError("snapshot incomplete: " + part)
    output.mkdir(parents=True)
    try:
        sqlite = stage_incremental_sqlite(
            old / "rag_index.sqlite3", new / "rag_index.sqlite3",
            output / "rag_index.sqlite3", project_id)
        if fail_after == "sqlite":
            raise IncrementalBundleError("injected failure after sqlite")
        manifest = stage_incremental_manifest(
            old / "rag-index-manifest.json", new / "rag-index-manifest.json",
            output / "rag-index-manifest.json", project_id)
        if fail_after == "manifest":
            raise IncrementalBundleError("injected failure after manifest")
        vectors = stage_incremental_qdrant(
            old / "qdrant", new / "qdrant", output / "qdrant", project_id)
        if fail_after == "qdrant":
            raise IncrementalBundleError("injected failure after qdrant")
        # validate_staged_index is single-project only and does not support
        # a merged multi-project store. Full cross-store validation is pending.
        return {"state": "BUNDLE_STAGED_NOT_PUBLISHED",
                "sqlite": sqlite, "manifest": manifest, "qdrant": vectors,
                "validated_for_publish": False, "destination": str(output)}
    except BaseException:
        shutil.rmtree(output, ignore_errors=True)
        raise
