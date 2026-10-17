"""Lab-only Windows handle and sidecar preflight for synthetic RAG stores.

This probe cannot prove mmap release or full production quiescence.
"""
from __future__ import annotations

from pathlib import Path
import hashlib

from rag.runtime.offline_fixture_snapshot import _root, _redirected, _hash_tree
from rag.runtime.offline_fixture_file_guard import hold_fixture_files_readonly


def inspect_fixture_handles(root_path):
    report = {"state": "BLOCKED", "files_checked": 0, "issues": [],
              "copy_authorized": False, "all_handles_closed": False,
              "production_quiescence_proven": False}
    try:
        root = _root(root_path)
        sqlite_file = root / "rag_index.sqlite3"
        manifest = root / "rag-index-manifest.json"
        vectors = root / "qdrant"
        sidecars = [root / ("rag_index.sqlite3" + suffix)
                    for suffix in ("-wal", "-shm", "-journal")]
        if any(p.exists() or _redirected(p) for p in sidecars):
            report["issues"].append("SQLITE_SIDECAR_PRESENT")
            return report
        if not vectors.is_dir() or _redirected(vectors):
            report["issues"].append("VECTOR_DIR_MISSING_OR_REDIRECTED")
            return report
        entries = sorted(vectors.rglob("*"))
        if any(_redirected(p) for p in entries):
            report["issues"].append("VECTOR_TREE_REDIRECTED")
            return report
        files = [sqlite_file, manifest]
        files.extend(p for p in entries if p.is_file())
        if len(files) < 3:
            report["issues"].append("INCOMPLETE_SYNTHETIC_STORES")
            return report
        for p in files:
            if not p.is_file() or _redirected(p) or p.stat().st_nlink > 1:
                report["issues"].append("REDIRECTED_OR_MISSING_SOURCE")
                return report
        with hold_fixture_files_readonly(files):
            def fingerprints():
                result = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in (sqlite_file, manifest)}
                result.update({"qdrant/" + key: value
                               for key, value in _hash_tree(vectors).items()})
                return result
            before = fingerprints()
            after = fingerprints()
            current_entries = sorted(vectors.rglob("*"))
            if current_entries != entries or before != after:
                report["issues"].append("STORES_CHANGED_DURING_READ")
                return report
            report["files_checked"] = len(files)
        report["state"] = "LAB_HANDLES_READABLE_UNPROVEN"
    except (OSError, ValueError, RuntimeError) as exc:
        report["issues"].append(type(exc).__name__)
    return report
