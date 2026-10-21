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