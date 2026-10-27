"""RAG-AUTO-05-E preflight blueprint, no writes, no worker or publication."""
from __future__ import annotations

from rag.runtime.auto_index_incremental_plan import IncrementalPlanError


def build_incremental_execution_blueprint(
    delta: dict, chunk_receipt: dict, vector_proof: dict,
) -> dict:
    """Reconcile three independent receipts before allowing future staging."""
    if not all(isinstance(value, dict)
               for value in (delta, chunk_receipt, vector_proof)):
        raise IncrementalPlanError("missing incremental receipts")
    if (delta.get("mode") != "PLAN_ONLY"
            or chunk_receipt.get("mode") != "CHUNK_RECEIPT_ONLY"
            or vector_proof.get("mode") != "VECTOR_RECEIPTS_VERIFIED"):
        raise IncrementalPlanError("incremental receipts incompatible")
    if (delta.get("reuse_authorized") is not False
            or chunk_receipt.get("vector_copy_authorized") is not False
            or vector_proof.get("copy_executed") is not False):
        raise IncrementalPlanError("unexpected mutation in prior stage")
    reuse, reindex = delta.get("eligible_reuse_sources"), delta.get("reindex_sources")
    removed = delta.get("removed_sources")
    candidates = chunk_receipt.get("candidate_chunk_ids")
    if (not isinstance(reuse, list) or not isinstance(reindex, list)
            or not isinstance(removed, list) or not isinstance(candidates, dict)
            or any(not isinstance(name, str) for name in reuse + reindex + removed)):
        raise IncrementalPlanError("malformed source proposal")
    if (len(set(reuse)) != len(reuse) or len(set(reindex)) != len(reindex)
            or len(set(removed)) != len(removed)
            or set(reuse) != set(candidates)
            or set(reuse) & set(reindex)
            or set(removed) & (set(reuse) | set(reindex))):
        raise IncrementalPlanError("source plan inconsistencies")
    ids = [chunk for values in candidates.values()
           for chunk in values] if all(isinstance(values, list)
                                      for values in candidates.values()) else None
    if ids is None or any(not isinstance(value, str) for value in ids):
        raise IncrementalPlanError("invalid chunk receipts")
    if (len(ids) != len(set(ids))
            or chunk_receipt.get("candidate_vector_count") != len(ids)
            or vector_proof.get("checked_vectors") != len(ids)
            or vector_proof.get("source_count") != len(reuse)):
        raise IncrementalPlanError("reuse vector receipt count mismatch")
    return {
        "schema_version": 1,
        "mode": "ISOLATED_STAGE_PREFLIGHT_ONLY",
        "reuse_source_count": len(reuse),
        "reuse_vector_count": len(ids),
        "reindex_sources": sorted(reindex),
        "drop_sources": sorted(removed),
        "work_items": [{"path": p, "action": "EMBED"} for p in sorted(reindex)],
        "review_required": True,
        "worker_started": False,
        "vectors_written": False,
        "public_pointer_updated": False,
        "stage_approved": False,
    }
