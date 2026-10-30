"""RAG-DEL evidence bundle: read-only cross-check across candidate artifacts.

The bundle is a *review artifact*, not a runtime generation receipt.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from rag.runtime.knowledge_deletion_evidence import inspect_deletion_candidate_evidence
from rag.runtime.knowledge_deletion_qdrant_freeze import (
    fingerprint_closed_qdrant_store, verify_closed_qdrant_inventory,
)

class DeletionBundleError(RuntimeError):
    pass

def prepare_deletion_review_bundle(stage_path: str | Path) -> dict:
    """Inspect previously sealed SQLite/manifest + closed Qdrant in stage."""
    stage=Path(stage_path)
    evidence=inspect_deletion_candidate_evidence(stage)
    if evidence.get("activation_authorized") is not False:
        raise DeletionBundleError("unexpected activation authorization")
    physical=fingerprint_closed_qdrant_store(stage/"qdrant")
    payload={
        "schema_version":1,
        "state":"DELETION_CANDIDATE_REVIEW_ONLY",
        "project_id":evidence["project_id"],
        "baseline_generation":evidence["baseline_generation"],
        "selection_sha256":evidence["selection_sha256"],
        "sqlite_manifest_receipt_sha256":evidence["receipt_sha256"],
        "qdrant_inventory_sha256":physical["inventory_sha256"],
        "qdrant_total_files":physical["total_files"],
        "qdrant_total_bytes":physical["total_bytes"],
        "activation_authorized":False,
        "public_pointer_updated":False,
        "operational_use_allowed":False,
    }
    canonical=json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")
    payload["bundle_sha256"]=sha256(canonical).hexdigest()
    return payload

def verify_deletion_review_bundle(stage_path: str | Path, expected: dict) -> dict:
    if (not isinstance(expected,dict)
            or expected.get("state")!="DELETION_CANDIDATE_REVIEW_ONLY"
            or expected.get("activation_authorized") is not False
            or expected.get("operational_use_allowed") is not False):
        raise DeletionBundleError("invalid review bundle")
    current=prepare_deletion_review_bundle(stage_path)
    if current!=expected:
        raise DeletionBundleError("candidate bundle changed after review")
    return {"state":"DELETION_REVIEW_BUNDLE_MATCHED",
            "bundle_sha256":current["bundle_sha256"],
            "activation_authorized":False,
            "operational_use_allowed":False}
