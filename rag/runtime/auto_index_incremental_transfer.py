"""RAG-AUTO-05-E: verified source to approved isolated candidate, bounded.

Not scheduled automatically. Does not start Jina or activate catalog/public
generation. A single TEXT or CODE batch with deterministic provenance.
"""
from __future__ import annotations

from pathlib import Path

from rag.runtime.auto_index_incremental_review import plan_reviewed_incremental_delta
from rag.runtime.auto_index_queue import get_job
from rag.runtime.auto_index_approval import read_reviewed_sources
from rag.runtime.auto_index_generation import verify_prepared_auto_generation
from rag.runtime.auto_index_incremental_read import read_reusable_vectors
from rag.runtime.auto_index_incremental_batches import partition_reuse_receipt
from rag.runtime.auto_index_incremental_adapter import import_into_approved_auto_stage
from rag.runtime.auto_index_staging import stage_directory
from rag.runtime.auto_index_incremental_verify import verify_isolated_reuse_batch
from rag.runtime.auto_index_incremental_plan import IncrementalPlanError
from rag.index.qdrant_local import open_qdrant_local,close_qdrant_local


def transfer_verified_incremental_batch(
    queue_path: Path, baseline_job_id: str, candidate_job_id: str, *,
    baseline_text_model: str, candidate_text_model: str,
    baseline_code_model: str, candidate_code_model: str,
    operator_approved: bool = False, max_vectors: int = 256,
    batch_id: str | None = None, batch_index: int = 0,
) -> dict:
    if operator_approved is not True:
        raise PermissionError("verified incremental transfer needs explicit approval")
    planned=plan_reviewed_incremental_delta(
        queue_path,baseline_job_id,candidate_job_id,
        baseline_text_model=baseline_text_model,
        candidate_text_model=candidate_text_model,
        baseline_code_model=baseline_code_model,
        candidate_code_model=candidate_code_model,
    )
    receipt=planned["candidate_reuse_chunk_receipt"]
    if receipt.get("project_id") != planned["project_id"]:
        raise IncrementalPlanError("candidate chunk receipt project drift")
    source=verify_prepared_auto_generation(queue_path,baseline_job_id)
    if source.get("verified") is not True or source.get("project_id") != planned["project_id"]:
        raise IncrementalPlanError("baseline validation drift")
    source_root=Path(source["generation"])
    folder=source_root/"qdrant"
    if not folder.is_dir() or folder.is_symlink() or (
        hasattr(folder,"is_junction") and folder.is_junction()
    ):
        raise IncrementalPlanError("baseline vector store is not a safe directory")
    approved=read_reviewed_sources(queue_path,baseline_job_id)
    batches=partition_reuse_receipt(receipt,approved,max_vectors=max_vectors)
    if (not isinstance(batch_index,int) or isinstance(batch_index,bool)
            or batch_index < 0 or batch_index >= len(batches)):
        raise IncrementalPlanError("invalid or unavailable incremental batch index")
    receipt=batches[batch_index]
    count=receipt["candidate_vector_count"]
    kinds={item["index_kind"] for item in approved["sources"]
           if item["path"] in receipt["candidate_chunk_ids"]}
    if len(kinds) != 1:
        raise IncrementalPlanError("only one model collection per import batch")
    client=open_qdrant_local(folder)
    try:
        records=read_reusable_vectors(client,receipt,approved,max_vectors=max_vectors)
    finally:
        close_qdrant_local(client)
    imported=import_into_approved_auto_stage(
        queue_path,candidate_job_id,receipt,approved,records,
        operator_approved=True,max_vectors=max_vectors,batch_id=batch_id,
    )
    stage=stage_directory(queue_path,candidate_job_id)
    target=open_qdrant_local(stage/"qdrant")
    try:
        verification=verify_isolated_reuse_batch(
            target,stage,imported["batch_id"],receipt,approved,
            max_vectors=max_vectors,
        )
    finally:
        close_qdrant_local(target)
    if verification.get("revalidation_passed") is not True:
        raise IncrementalPlanError("candidate copy failed post-write verification")
    return {
        **imported,
        "post_copy_verification":verification,
        "baseline_job_id":baseline_job_id,
        "candidate_job_id":candidate_job_id,
        "batch_index":batch_index,
        "batch_count":len(batches),
        "provenance_verified":True,
        "needs_post_copy_validation":True,
        "public_pointer_updated":False,
    }
