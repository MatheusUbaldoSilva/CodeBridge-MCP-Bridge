"""RAG-AUTO-05-E non-mutating crash recovery inspection."""
from __future__ import annotations

from pathlib import Path

from rag.runtime.auto_index_incremental_checkpoint import read_isolated_batch_receipt
from rag.runtime.auto_index_incremental_plan import IncrementalPlanError


def inspect_incremental_stage_recovery(stage_path: Path, batch_id: str) -> dict:
    stage=Path(stage_path)
    if not stage.is_dir() or stage.is_symlink() or (
        hasattr(stage,"is_junction") and stage.is_junction()
    ):
        raise IncrementalPlanError("stage is missing or redirected")
    if not isinstance(batch_id,str) or len(batch_id)!=32 or any(
        ch not in "0123456789abcdef" for ch in batch_id
    ):
        raise IncrementalPlanError("invalid batch identifier")
    lock=stage/".ragauto05-active-batch.lock"
    temporary=stage/("batch_"+batch_id+".writing")
    committed=stage/("batch_"+batch_id+".json")
    locked=lock.exists() or lock.is_symlink()
    incomplete=temporary.exists() or temporary.is_symlink()
    completed=committed.exists() or committed.is_symlink()
    redirected=any(p.is_symlink() for p in (lock,temporary,committed))
    if redirected:
        state="REDIRECTED_RECOVERY_ARTIFACT"
    elif incomplete:
        state="INTERRUPTED_RECEIPT"
    elif completed:
        try:
            receipt=read_isolated_batch_receipt(stage,batch_id)
            state="CHECKPOINT_PRESENT_LOCKED" if locked else "CHECKPOINT_AWAITING_QDRANT"
        except (ValueError, OSError, KeyError, TypeError):
            state="INVALID_CHECKPOINT"
    elif locked:
        state="POSSIBLY_UNCHECKPOINTED_VECTORS"
    else:
        state="NOT_STARTED"
    return {
        "batch_id":batch_id,
        "state":state,
        "lock_present":locked,
        "checkpoint_present":completed,
        "interrupted_temp_present":incomplete,
        "redirected_artifact_present":redirected,
        "safe_to_auto_retry":False,
        "requires_manual_audit":state != "NOT_STARTED",
        "public_pointer_updated":False,
    }
