"""Independent lab-only restored snapshot audit. No production/activation access."""
from __future__ import annotations
import json
from pathlib import Path
from rag.runtime.offline_fixture_snapshot import _root, _hash_tree, _redirected
from rag.runtime.incremental_bundle_validate import validate_incremental_bundle

def audit_restored_fixture(fixture_root, backup_name, restore_name):
    result={"state":"BLOCKED","same_hashes":False,"same_semantic_content":False,
            "production_authorized":False,"publication_authorized":False,"issues":[]}
    try:
        root=_root(fixture_root)
        if any(not isinstance(x,str) or not x.isidentifier() for x in (backup_name,restore_name)):
            raise ValueError("invalid fixture names")
        saved=root/"offline-fixture-backups"/backup_name
        restored=root/"offline-fixture-restores"/restore_name/"snapshot"
        original=saved/"snapshot"
        report=saved/"report.json"
        for leaf in (saved, original, restored, report):
            if any(_redirected(part) for part in (leaf, *leaf.parents)):
                raise ValueError("redirected path")
        for payload in (original, restored):
            if any((payload / ("rag_index.sqlite3" + suffix)).exists()
                   for suffix in ("-wal", "-shm", "-journal")):
                raise ValueError("unexpected SQLite sidecar")
        if not original.is_dir() or not restored.is_dir() or not report.is_file():
            raise ValueError("incomplete fixture")
        meta=json.loads(report.read_text(encoding="utf-8"))
        if meta.get("production_authorized") is not False or meta.get("state")!="LAB_FIXTURE_SNAPSHOT_ONLY":
            raise ValueError("unsafe snapshot report")
        a=_hash_tree(original)
        b=_hash_tree(restored)
        if a!=b or a!=meta.get("hashes"):
            result["issues"].append("SNAPSHOT_RESTORE_HASH_MISMATCH")
            return result
        av=validate_incremental_bundle(original)
        bv=validate_incremental_bundle(restored)
        if av!=bv or av!=meta.get("verification"):
            result["issues"].append("CROSS_STORE_CONTENT_MISMATCH")
            return result
        # The verification itself can race an external writer; recheck both.
        if _hash_tree(original)!=a or _hash_tree(restored)!=b:
            result["issues"].append("STORES_CHANGED_DURING_VALIDATION")
            return result
        result.update(state="LAB_RESTORE_EQUIVALENCE_UNPROVEN_FOR_PRODUCTION",
                      same_hashes=True,same_semantic_content=True)
    except (OSError,ValueError,RuntimeError,TypeError,KeyError) as exc:
        result["issues"].append(type(exc).__name__)
    return result
