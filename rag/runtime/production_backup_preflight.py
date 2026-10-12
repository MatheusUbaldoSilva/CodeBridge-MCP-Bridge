"""Read-only production RAG backup gate: advisory, never authorizes copying.

Offline backup additionally requires an externally verified quiet period and
validation of the resulting SQLite+manifest+Qdrant snapshot.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import sqlite3

from rag.index.manifest import load_index_manifest


def inspect_backup_prerequisites(sqlite_path, manifest_path, qdrant_path,
                                 *, operator_asserted_quiesced=False):
    paths = [Path(path).resolve() for path in
             (sqlite_path, manifest_path, qdrant_path)]
    db, manifest, vectors = paths
    issues = []
    if not db.is_file():
        issues.append("SQLITE_MISSING")
    if not manifest.is_file():
        issues.append("MANIFEST_MISSING")
    if not vectors.is_dir():
        issues.append("QDRANT_MISSING")
    elif not any(vectors.iterdir()):
        issues.append("QDRANT_EMPTY")
    if not operator_asserted_quiesced:
        issues.append("APPLICATION_QUIESCENCE_NOT_CONFIRMED")
    if db.is_file():
        for suffix in ("-wal", "-shm", "-journal"):
            if db.with_name(db.name + suffix).exists():
                issues.append("SQLITE_SIDECAR_PRESENT")
                break

    documents = chunks = manifest_entries = None
    if db.is_file() and manifest.is_file() and "SQLITE_SIDECAR_PRESENT" not in issues:
        try:
            before = [(p.stat().st_size, p.stat().st_mtime_ns)
                      for p in (db, manifest)]
            conn = sqlite3.connect(db.as_uri() + "?mode=ro", uri=True)
            try:
                if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    issues.append("SQLITE_INTEGRITY_FAILED")
                rows = conn.execute(
                    "SELECT project_id,path,sha256 FROM rag_documents").fetchall()
                documents = len(rows)
                chunks = conn.execute("SELECT count(*) FROM rag_chunks").fetchone()[0]
            finally:
                conn.close()
            entries = load_index_manifest(manifest).entries
            manifest_entries = len(entries)
            observed = Counter((str(project), str(path), str(digest))
                               for project, path, digest in rows)
            expected = Counter((item.project_id, item.path, item.sha256)
                               for item in entries)
            if observed != expected:
                issues.append("MANIFEST_SQLITE_MISMATCH")
            after = [(p.stat().st_size, p.stat().st_mtime_ns)
                     for p in (db, manifest)]
            if before != after:
                issues.append("FILES_CHANGED_DURING_INSPECTION")
        except (OSError, sqlite3.Error, ValueError, RuntimeError, KeyError, TypeError):
            issues.append("UNREADABLE_OR_INVALID_INDEX")

    return {
        "state": "BLOCKED" if issues else "OFFLINE_CANDIDATE_REQUIRES_VERIFIED_SNAPSHOT",
        "issues": sorted(set(issues)),
        "documents": documents,
        "chunks": chunks,
        "manifest_entries": manifest_entries,
        "qdrant_present": vectors.is_dir(),
        "read_only": True,
        "copy_authorized": False,
        "publication_authorized": False,
    }
