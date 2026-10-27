"""RAG-AUTO-05-E guarded isolated approved-job import adapter.

This is not wired into the automatic scheduler. It can only write into
the auto-index staging directory resolved from the canonical queue/job.
"""
from __future__ import annotations

from pathlib import Path

from rag.runtime.auto_index_queue import get_job
from rag.runtime.auto_index_staging import stage_directory
from rag.index.qdrant_local import open_qdrant_local,close_qdrant_local
from rag.runtime.auto_index_incremental_execute import execute_isolated_reuse_batch
from rag.runtime.auto_index_incremental_sqlite import verify_candidate_stage_rows


def import_into_approved_auto_stage(
    queue_path: Path, job_id: str, receipt: dict, sources: dict,
    records: dict, *, operator_approved: bool = False,
    max_vectors: int = 256, batch_id: str | None = None,
) -> dict:
    if operator_approved is not True:
        raise PermissionError("operator approval required for isolated stage import")
    job=get_job(queue_path,job_id)
    if (job is None or job.get("approved") is not True
            or job.get("state") != "QUEUED"):
        raise PermissionError("job must have approved QUEUED state")
    if job.get("project_id") == "codebridge":
        raise PermissionError("public project is reserved")
    if receipt.get("project_id") != job.get("project_id"):
        raise PermissionError("vector project differs from approved job")
    stage=stage_directory(queue_path,job_id)
    if (not stage.is_dir() or stage.is_symlink()
            or (hasattr(stage,"is_junction") and stage.is_junction())):
        raise PermissionError("candidate staging root is missing or redirected")
    db=stage/"rag_index.sqlite3"
    qdrant=stage/"qdrant"
    if (not db.is_file() or not qdrant.is_dir()
            or db.is_symlink() or qdrant.is_symlink()
            or (hasattr(qdrant,"is_junction") and qdrant.is_junction())):
        raise PermissionError("candidate staging must be fully prepared and isolated")
    verify_candidate_stage_rows(db,job["project_id"],records)
    client=open_qdrant_local(qdrant)
    try:
        return execute_isolated_reuse_batch(
            client,stage,receipt,sources,records,
            approve_isolated_stage=True,max_vectors=max_vectors,
            batch_id=batch_id,
        )
    finally:
        close_qdrant_local(client)
