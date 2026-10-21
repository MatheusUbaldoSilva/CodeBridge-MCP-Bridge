"""Read-only exact source-scope review, never a production authorization.

Compares an independently provided, exact source SHA map against the closed
baseline/candidate review. The caller must separately obtain real operator
approval; this function cannot sign or activate anything.
"""
from __future__ import annotations

import re
from collections.abc import Mapping

_SHA = re.compile(r"^[0-9a-f]{64}$")


def inspect_approved_source_scope(review: dict, approved_sha256: Mapping[str, str],
                                  *, expected_fingerprint: str) -> dict:
    """Fail closed on any added/changed/removed source or fingerprint drift."""
    errors = []
    if not isinstance(review, dict) or review.get("state") != "CONTENT_COMPARISON_ONLY_NOT_APPROVED":
        errors.append("SOURCE_REVIEW_INVALID")
        review = {}
    fingerprint = review.get("evidence_sha256_not_signature")
    if not isinstance(expected_fingerprint, str) or not _SHA.fullmatch(expected_fingerprint):
        errors.append("EXPECTED_REVIEW_FINGERPRINT_INVALID")
    elif fingerprint != expected_fingerprint:
        errors.append("SOURCE_REVIEW_FINGERPRINT_CHANGED")
    if not isinstance(approved_sha256, Mapping) or not approved_sha256:
        errors.append("EXACT_SOURCE_APPROVAL_LIST_MISSING")
        approved_sha256 = {}
    elif any(not isinstance(k, str) or not k or not isinstance(v, str)
             or not _SHA.fullmatch(v) for k, v in approved_sha256.items()):
        errors.append("APPROVED_SOURCE_MAP_INVALID")
    if review.get("removed_paths"):
        errors.append("REMOVED_SOURCES_NOT_ALLOWED")
    changes = review.get("details")
    if not isinstance(changes, list) or any(not isinstance(c, dict) for c in changes):
        errors.append("SOURCE_CHANGE_DETAILS_INVALID")
        changes = []
    paths = []
    for item in changes:
        path = item.get("path")
        action = item.get("action")
        digest = item.get("candidate_sha256")
        if action not in ("ADDED", "MODIFIED") or not isinstance(path, str):
            errors.append("UNEXPECTED_SOURCE_CHANGE")
            continue
        paths.append(path)
        if not isinstance(digest, str) or approved_sha256.get(path) != digest:
            errors.append("SOURCE_HASH_NOT_IN_EXACT_APPROVAL_SCOPE")
    if len(paths) != len(set(paths)):
        errors.append("DUPLICATE_SOURCE_CHANGE")
    if set(paths) != set(approved_sha256):
        errors.append("SOURCE_PATH_SCOPE_MISMATCH")
    added, modified = review.get("added_paths"), review.get("modified_paths")
    removed = review.get("removed_paths")
    if not isinstance(added, list) or not isinstance(modified, list) or not isinstance(removed, list):
        errors.append("REVIEW_PATH_LISTS_INVALID")
    elif (any(not isinstance(path, str) for path in added + modified + removed)
          or sorted(paths) != sorted(added + modified)):
        errors.append("REVIEW_DETAILS_PATHS_DISAGREE")
    return {
        "state": "SCOPE_MATCHED_NOT_AUTHORIZED" if not errors else "SCOPE_BLOCKED",
        "issues": sorted(set(errors)), "source_count": len(paths),
        "read_only": True, "activation_authorized": False,
        "safe_to_publish": False,
    }
