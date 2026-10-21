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
