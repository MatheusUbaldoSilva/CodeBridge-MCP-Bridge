"""RAG-AUTO-05-E: verify transferred Qdrant points against durable batch receipt.

No public activation. Verification occurs after the write and checks all
expected point IDs, provenance, dimensions and receipt integrity again.
"""
from __future__ import annotations

from pathlib import Path

from rag.runtime.auto_index_incremental_checkpoint import read_isolated_batch_receipt
from rag.runtime.auto_index_incremental_plan import IncrementalPlanError
from rag.runtime.auto_index_incremental_read import read_reusable_vectors


def verify_isolated_reuse_batch(
    destination, stage_path: Path, batch_id: str,
    chunk_receipt: dict, source_receipt: dict, *,
    max_vectors: int = 256,
) -> dict:
    receipt=read_isolated_batch_receipt(stage_path,batch_id)
    records=read_reusable_vectors(
        destination,chunk_receipt,source_receipt,max_vectors=max_vectors,
    )
    count=sum(len(records[kind]) for kind in ("TEXT","CODE"))
    if count != receipt["vectors_written"]:
        raise IncrementalPlanError("checkpoint count differs from persisted Qdrant")
    return {
        "mode":"ISOLATED_BATCH_VERIFIED",
        "batch_id":batch_id,
        "checked_vectors":count,
        "receipt_sha256":receipt["receipt_sha256"],
        "revalidation_passed":True,
        "generation_activated":False,
        "public_pointer_updated":False,
    }
