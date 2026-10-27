"""RAG-AUTO-05-E isolated import orchestration with recoverable receipt.

The caller provides an empty isolated Qdrant client and its stage directory.
This is deliberately not a production scheduler or public generation API.
"""
from __future__ import annotations

from pathlib import Path
import uuid

from rag.runtime.auto_index_incremental_stage_write import import_verified_reuse_batch
from rag.runtime.auto_index_incremental_checkpoint import persist_isolated_batch_receipt


def execute_isolated_reuse_batch(
    destination, stage_path: Path, receipt: dict, sources: dict, records: dict,
    *, approve_isolated_stage: bool = False, batch_id: str | None = None,
    max_vectors: int = 256,
) -> dict:
    if approve_isolated_stage is not True:
        raise PermissionError("isolated batch execution requires explicit approval")
    if destination is None:
        raise ValueError("destination cannot be None")
    stage=Path(stage_path)
    if not stage.is_dir() or stage.is_symlink() or (
        hasattr(stage, "is_junction") and stage.is_junction()
    ):
        raise ValueError("stage root must be an existing ordinary directory")
    token=batch_id if batch_id is not None else uuid.uuid4().hex
    if not isinstance(token,str) or len(token)!=32 or any(
        char not in "0123456789abcdef" for char in token
    ):
        raise ValueError("invalid batch id")
    if (stage/("batch_"+token+".json")).exists() or (
        stage/("batch_"+token+".writing")
    ).exists():
        raise ValueError("existing batch receipt requires recovery audit")
    lock=stage/".ragauto05-active-batch.lock"
    # Exclusive creation is atomic even for concurrent workers. A stale
    # lock must be inspected manually, never broken by automatic retry.
    with lock.open("x",encoding="ascii") as handle:
        handle.write(token)
        handle.flush()
    try:
        result=import_verified_reuse_batch(
            destination,receipt,sources,records,
            isolated_destination=True,allow_stage_write=True,
            max_vectors=max_vectors,
        )
        checkpoint=persist_isolated_batch_receipt(
            stage,token,result,allow_write=True,
        )
    except Exception as exc:
        raise RuntimeError(
            "isolated stage may contain incomplete vectors; inspect lock and rebuild"
        ) from exc
    lock.unlink()
    return {
        "batch_id":token,**result,**checkpoint,
        "recovery_state":"REVALIDATE_BEFORE_RESUME",
        "generation_activated":False,
        "public_pointer_updated":False,
    }
