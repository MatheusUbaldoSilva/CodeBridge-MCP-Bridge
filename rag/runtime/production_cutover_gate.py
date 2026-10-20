"""Read-only readiness gate for CodeBridge RAG V1 generation cutover.

Verifies both immutable generation candidates, legacy integrity and source
provenance. This module never creates a pointer, approves activation or writes
to active SQLite / Qdrant. It intentionally fails closed pending MCP reload
and atomic recovery protocol completion.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

from rag.runtime.status import resolve_rag_sqlite_path
from rag.runtime.live_integrity import inspect_live_index


_PROTECTED = (
    "rag_index.sqlite3", "rag-index-manifest.json", "qdrant/meta.json",
    "qdrant/collection/text/storage.sqlite",
    "qdrant/collection/code/storage.sqlite",
)


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _verify_versioned(root: Path, name: str, label: str) -> dict:
    if not name.startswith("v1_" + label + "_"):
        raise ValueError("unexpected versioned generation identifier")
    parent = (root / "generations").resolve()
    directory = (parent / name).resolve(strict=True)
    if not directory.is_relative_to(parent) or not directory.is_dir():
        raise ValueError("generation root outside CodeBridge versioned storage")
    file = directory / "generation-receipt.json"
    data = json.loads(file.read_text(encoding="utf-8"))
    if (data.get("status") != "VERSIONED_GENERATION_VALIDATED_NOT_ACTIVE"
            or data.get("generation") != name
            or data.get("label") != label
            or data.get("activation_permitted") is not False):
        raise ValueError("generation identity or no-activation receipt invalid")
    for relative in _PROTECTED:
        if _sha(directory / relative) != data["file_sha256"][relative]:
            raise ValueError("versioned bundle hash drift: " + relative)
    # Embedded MCP Python lacks qdrant-client. Reuse the full read-only
    # SQLite/Qdrant identity verifier, not a count-only fallback.
    from rag.runtime.versioned_live_integrity import inspect_pinned_index
    from rag.runtime.production_generation_read import SearchStoragePaths
    pinned = SearchStoragePaths(
        generation=name,
        sqlite=directory / "rag_index.sqlite3",
        qdrant=directory / "qdrant",
        manifest=directory / "rag-index-manifest.json",
    )
    observed = inspect_pinned_index(pinned)
    validated = data["validation"]
    if (observed["documents"] != validated.get("documents")
            or observed["chunks"] != validated.get("chunks")
            or observed["manifest_entries"] != validated.get("manifest_entries")
            or sum(c["vectors"] for c in observed["collections"].values())
                != validated.get("vectors")):
        raise ValueError("versioned bundle changed since receipt")
    # Index state is consumed by public status/health checks; a merged
    # generation with stale counts is not safe to activate even when vector
    # identities and manifest hashes are otherwise consistent.
    sqlite_path = directory / "rag_index.sqlite3"
    db = sqlite3.connect(sqlite_path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        counts = db.execute(
            "SELECT document_count, chunk_count, state FROM rag_index_state "
            "WHERE project_id='codebridge'"
        ).fetchone()
    finally:
        db.close()
    if counts != (validated["documents"], validated["chunks"], "READY"):
        raise ValueError("generation index_state metadata differs from content")
    return {"generation": name, "validation": validated, "sha_verified": True}



def _summarize_manifest_delta(baseline_manifest: Path, candidate_manifest: Path) -> dict:
    """Read-only exact source/chunk delta between two validated closed bundles."""
    from rag.index.manifest import load_index_manifest

    old = load_index_manifest(baseline_manifest)
    updated = load_index_manifest(candidate_manifest)
    before = {e.key: e for e in old.entries}
    after = {e.key: e for e in updated.entries}
    added = sorted(after[key].path for key in after.keys() - before.keys())
    removed = sorted(before[key].path for key in before.keys() - after.keys())
    modified = sorted(
        after[key].path for key in before.keys() & after.keys()
        if (before[key].sha256 != after[key].sha256
            or before[key].chunk_ids != after[key].chunk_ids)
    )
    return {
        "added_count": len(added), "added_paths": added,
        "modified_count": len(modified), "modified_paths": modified,
        "removed_count": len(removed), "removed_paths": removed,
        "unchanged_count": len(before.keys() & after.keys()) - len(modified),
        "before_entries": len(before), "after_entries": len(after),
        "operator_content_review_attested": False,
        "read_only": True,
    }

def assess_real_cutover(baseline: str, candidate: str) -> dict:
    state = resolve_rag_sqlite_path().resolve().parent
    if state.name != "rag" or state.parent.name != "CodeBridge":
        raise ValueError("not a real CodeBridge RAG installation")
    blockers = [
        "PUBLIC_MCP_READERS_RESTART_NOT_ATTESTED",
        "ATOMIC_PRODUCTION_POINTER_WRITER_AND_ROLLBACK_NOT_VALIDATED",
    ]
    reasons = []
    checked = {}
    try:
        base = _verify_versioned(state, baseline, "base")
        updated = _verify_versioned(state, candidate, "delta")
        checked["baseline"] = base
        checked["candidate"] = updated
        # Cross-store hashes prove the candidate is internally immutable, not
        # that its indexed source text still matches the current checkout.
        # Reuse the indexer's decoded-text SHA contract: CRLF-only checkouts
        # do not count as semantic content drift.
        from rag.runtime.production_source_freshness import (
            assess_generation_source_freshness,
        )
        freshness = assess_generation_source_freshness(
            state / "generations" / candidate,
            Path.home() / "CodeBridge-MCP-Bridge",
        )
        checked["candidate_source_freshness"] = freshness
        if freshness["state"] != "SOURCE_SNAPSHOT_CURRENT":
            reasons.append("CANDIDATE_SOURCE_DRIFT_REQUIRES_REINDEX")
        before = base["validation"]
        after = updated["validation"]
        manifest_delta = _summarize_manifest_delta(
            state / "generations" / baseline / "rag-index-manifest.json",
            state / "generations" / candidate / "rag-index-manifest.json",
        )
        checked["candidate_manifest_delta"] = manifest_delta
        # A revised source can have any number of new chunks; hard-coding
        # +5 vectors (the initial one-file smoke case) incorrectly rejects
        # legitimate subsequent incremental replacements. Instead require
        # identical source coverage apart from the specific new document,
        # no removals, and full cross-store counts already verified above.
        if (
            manifest_delta["removed_count"] != 0
            or manifest_delta["added_count"] != 1
            or after["documents"] != before["documents"] + manifest_delta["added_count"]
            or after["chunks"] != after["vectors"]
            or after["chunks"] < after["documents"]
        ):
            reasons.append("UNEXPECTED_GENERATION_DELTA")
        # This is evidence of changed files, NOT an operator's approval of
        # their hashes. The public cutover remains blocked independently.
        if manifest_delta["modified_count"] > 0:
            reasons.append("CHANGED_SOURCE_CONTENT_REVIEW_NOT_ATTESTED")
        active = inspect_live_index()
        checked["legacy"] = {
            "documents": active["documents"], "chunks": active["chunks"],
        }
        if (active["documents"] != before["documents"]
                or active["chunks"] != before["chunks"]):
            reasons.append("LEGACY_INDEX_DRIFT")
    except (OSError, ValueError, KeyError, RuntimeError, ImportError) as exc:
        reasons.append("INTEGRITY_PROOF_FAILED: " + str(exc))
    if (state / "production-generation-transition.json").exists():
        reasons.append("RECOVERY_JOURNAL_PENDING")
    if (state / "active-generation.json").exists():
        reasons.append("ACTIVE_POINTER_ALREADY_EXISTS")
    return {
        "state": "BLOCKED" if blockers or reasons else "READY",
        "safe_to_activate": False,
        "read_only": True,
        "blockers": blockers + reasons,
        "verified": checked,
        "recovery_preserved": True,
        "pointer_updated": False,
    }
