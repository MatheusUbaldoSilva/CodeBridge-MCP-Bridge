"""Read-only eligibility of the closed V1 incremental source delta.

A scope match is evidence for a future operator decision, not permission
to activate a generation or bypass the existing supervised cutover gate.
"""
from __future__ import annotations

from rag.runtime.production_source_scope_attestation import inspect_approved_source_scope

_INCREMENTAL_PATH = "rag/runtime/incremental_scheduler_gate.py"


def inspect_incremental_candidate_review(
    review: dict, approved_sha256: dict[str, str], *, expected_fingerprint: str,
    baseline_generation: str, candidate_generation: str,
) -> dict:
    scope = inspect_approved_source_scope(
        review, approved_sha256, expected_fingerprint=expected_fingerprint,
    )
    issues = list(scope["issues"])
    if not baseline_generation or not candidate_generation or baseline_generation == candidate_generation:
        issues.append("GENERATION_IDENTITY_INVALID")
    if review.get("added_paths") != [_INCREMENTAL_PATH] or review.get("modified_paths") != [] or review.get("removed_paths") != []:
        issues.append("INCREMENTAL_CANDIDATE_DELTA_MISMATCH")
    if review.get("base_entries") != 210 or review.get("candidate_entries") != 211:
        issues.append("GENERATION_DOCUMENT_COUNTS_MISMATCH")
    if not isinstance(review.get("unchanged_count"), int) or review["unchanged_count"] != 210:
        issues.append("BASELINE_SOURCE_COUNT_MISMATCH")
    return {
        "state": "CANDIDATE_SCOPE_VERIFIED_NOT_AUTHORIZED" if not issues else "BLOCKED",
        "issues": sorted(set(issues)),
        "baseline_generation": baseline_generation,
        "candidate_generation": candidate_generation,
        "source_count": scope["source_count"],
        "read_only": True,
        "activation_authorized": False,
        "safe_to_publish": False,
        "legacy_supervised_gate_unchanged": True,
    }


def review_closed_incremental_generations(
    baseline_dir, candidate_dir, approved_sha256: dict[str, str],
    *, expected_fingerprint: str,
) -> dict:
    """Review actual closed source stores; never touch active/published pointers."""
    from pathlib import Path
    from rag.runtime.production_content_review import summarize_versioned_source_review

    base = Path(baseline_dir)
    candidate = Path(candidate_dir)
    report = summarize_versioned_source_review(base, candidate)
    return inspect_incremental_candidate_review(
        report, approved_sha256, expected_fingerprint=expected_fingerprint,
        baseline_generation=report["baseline"],
        candidate_generation=report["candidate"],
    )

def inspect_offline_candidate_counts(baseline_dir, candidate_dir) -> dict:
    """Verify exact persisted counts using SQLite read-only, without publication."""
    import sqlite3
    from contextlib import closing
    from pathlib import Path

    actual = []
    issues = []
    for location, expected in ((baseline_dir, (210, 8761, "READY")),
                               (candidate_dir, (211, 8763, "READY"))):
        database = Path(location) / "rag_index.sqlite3"
        if not database.is_file():
            issues.append("CLOSED_SQLITE_MISSING")
            actual.append(None)
            continue
        try:
            with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as db:
                row = db.execute(
                    "SELECT document_count,chunk_count,state FROM rag_index_state "
                    "WHERE project_id='codebridge'"
                ).fetchone()
            actual.append(tuple(row) if row is not None else None)
            if row != expected:
                issues.append("CLOSED_GENERATION_COUNT_MISMATCH")
        except (sqlite3.Error, OSError, ValueError):
            issues.append("CLOSED_SQLITE_INVALID")
            actual.append(None)
    return {
        "state": "COUNTS_MATCH_NOT_AUTHORIZED" if not issues else "BLOCKED",
        "issues": sorted(set(issues)),
        "baseline_counts": actual[0],
        "candidate_counts": actual[1],
        "read_only": True,
        "activation_authorized": False,
        "safe_to_publish": False,
        "integrity_proved": False,
    }

def inspect_offline_candidate_sources(baseline_dir, candidate_dir, expected_source_sha256: str) -> dict:
    """Cross-check exact source delta in closed SQLite and manifests, read-only."""
    from pathlib import Path
    from rag.chunking.provenance import source_sha256
    from rag.index.manifest import load_index_manifest
    from rag.runtime.production_content_review import _closed_source

    counts = inspect_offline_candidate_counts(baseline_dir, candidate_dir)
    issues = list(counts["issues"])
    details = {}
    if not isinstance(expected_source_sha256, str) or len(expected_source_sha256) != 64:
        issues.append("EXPECTED_SOURCE_SHA_INVALID")
    try:
        before = _closed_source(Path(baseline_dir))
        after = _closed_source(Path(candidate_dir))
        base_manifest = load_index_manifest(Path(baseline_dir) / "rag-index-manifest.json")
        next_manifest = load_index_manifest(Path(candidate_dir) / "rag-index-manifest.json")
        left = {e.path: e for e in base_manifest.entries if e.project_id == "codebridge"}
        right = {e.path: e for e in next_manifest.entries if e.project_id == "codebridge"}
        added = sorted(set(after) - set(before))
        removed = sorted(set(before) - set(after))
        modified = sorted(path for path in set(after) & set(before)
                          if after[path] != before[path]
                          or left[path].chunk_ids != right[path].chunk_ids)
        expected = _INCREMENTAL_PATH
        if added != [expected] or removed or modified:
            issues.append("OFFLINE_SOURCE_DELTA_MISMATCH")
        if set(left) != set(before) or set(right) != set(after):
            issues.append("MANIFEST_SQLITE_SOURCE_MISMATCH")
        elif any(left[p].sha256 != before[p][1] for p in before) or any(
                right[p].sha256 != after[p][1] for p in after):
            issues.append("MANIFEST_SOURCE_SHA_MISMATCH")
        if expected not in after or after[expected][1] != expected_source_sha256:
            issues.append("INCREMENTAL_SOURCE_SHA_MISMATCH")
        details = {"added_paths": added, "removed_paths": removed,
                   "modified_paths": modified}
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        issues.append("OFFLINE_SOURCE_REVIEW_INVALID:" + type(exc).__name__)
    return {
        "state": "OFFLINE_SOURCE_SCOPE_MATCH_NOT_AUTHORIZED" if not issues else "BLOCKED",
        "issues": sorted(set(issues)), "details": details,
        "baseline_counts": counts["baseline_counts"],
        "candidate_counts": counts["candidate_counts"],
        "read_only": True, "activation_authorized": False,
        "safe_to_publish": False, "vector_integrity_proved": False,
    }