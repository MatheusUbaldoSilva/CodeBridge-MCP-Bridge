"""Read-only, deterministic identity for a reviewed incremental preview.

The SHA-256 digest is a content fingerprint, NOT an authentication token.
Neither this module nor its callers grant production publication permission.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path

from rag.runtime.incremental_preview_confirmation import revalidate_preview


def build_review_contract(snapshot, project, folder):
    """Validate live inputs and identify exactly the project/folder/file hashes reviewed."""
    result = revalidate_preview(snapshot, project, folder)
    hashes = snapshot["sha256"]
    scope = {
        "schema_version": 1,
        "project": project,
        "folder": str(Path(folder).resolve()),
        "sha256": dict(sorted(hashes.items())),
    }
    canonical = json.dumps(scope, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {
        "schema_version": 1,
        "project": project,
        "folder": scope["folder"],
        "files_checked": result["files_checked"],
        "review_sha256": fingerprint,
    }


def verify_review_contract(snapshot, project, folder, contract):
    """Fail closed for a changed scope, file or fabricated/mismatched receipt."""
    if not isinstance(contract, dict):
        raise ValueError("missing review contract")
    current = build_review_contract(snapshot, project, folder)
    if set(contract) != set(current):
        raise ValueError("review contract fields do not match")
    if any(contract[key] != current[key] for key in (
            "schema_version", "project", "folder", "files_checked")):
        raise ValueError("review scope does not match")
    digest = contract["review_sha256"]
    if not isinstance(digest, str) or not hmac.compare_digest(
            digest, current["review_sha256"]):
        raise ValueError("review fingerprint does not match")
    return current
