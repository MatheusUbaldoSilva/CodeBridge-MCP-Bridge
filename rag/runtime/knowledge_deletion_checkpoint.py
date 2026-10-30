"""RAG-DEL-01.03-B: durable batch receipts with Qdrant revalidation.

Does not open collections, switch generations, or alter public indexes.
"""
from __future__ import annotations

from pathlib import Path

from rag.runtime.auto_index_incremental_checkpoint import (
    persist_isolated_batch_receipt, read_isolated_batch_receipt,
)
from rag.runtime.auto_index_incremental_verify import verify_isolated_reuse_batch
from rag.runtime.auto_index_incremental_plan import IncrementalPlanError


def checkpoint_survivor_batch(
    destination_client, stage_root: str | Path, batch_id: str,
    copy_result: dict, batch_receipt: dict, source_receipt: dict, *,
    operator_approved: bool = False, max_vectors: int = 256,
) -> dict:
    """Persist and verify an imported batch in caller-validated private stage."""
    if operator_approved is not True:
        raise PermissionError("explicit isolated checkpoint approval required")
    if (not isinstance(copy_result, dict)
            or copy_result.get("state") != "SURVIVOR_BATCH_READBACK_VERIFIED"
            or copy_result.get("generation_activated") is not False
            or copy_result.get("requires_durable_checkpoint") is not True):
        raise IncrementalPlanError("batch was not readback verified")
    count=copy_result.get("vectors_verified")
    if type(count) is not int or not 1 <= count <= max_vectors:
        raise IncrementalPlanError("invalid checkpoint vector count")
    if (not isinstance(batch_receipt, dict)
            or batch_receipt.get("candidate_vector_count") != count
            or batch_receipt.get("vector_copy_authorized") is not False):
        raise IncrementalPlanError("batch receipt count or provenance mismatch")
    staged=Path(stage_root)
    record={
        "mode":"ISOLATED_STAGE_BATCH_WRITTEN",
        "vectors_written":count,
        "public_pointer_updated":False,
        "requires_staging_revalidation":True,
    }
    saved=persist_isolated_batch_receipt(
        staged,batch_id,record,allow_write=True,
    )
    verified=verify_isolated_reuse_batch(
        destination_client,staged,batch_id,batch_receipt,source_receipt,
        max_vectors=max_vectors,
    )
    if verified.get("revalidation_passed") is not True or verified.get("checked_vectors") != count:
        raise IncrementalPlanError("durable vector batch verification failed")
    return {
        "state":"SURVIVOR_BATCH_DURABLY_VERIFIED",
        "batch_id":batch_id,
        "vectors_verified":count,
        "receipt_sha256":saved["receipt_sha256"],
        "generation_activated":False,
        "public_pointer_updated":False,
    }


def inspect_survivor_batch_checkpoint(stage_root: str | Path, batch_id: str) -> dict:
    """Receipt-only recovery inspection; it cannot establish Qdrant validity."""
    record=read_isolated_batch_receipt(Path(stage_root),batch_id)
    return {
        "state":"NEEDS_QDRANT_REVALIDATION",
        "batch_id":batch_id,
        "vectors_declared":record["vectors_written"],
        "receipt_sha256":record["receipt_sha256"],
        "generation_activated":False,
    }
