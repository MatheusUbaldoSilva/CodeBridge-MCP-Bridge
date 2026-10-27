"""RAG-AUTO-05-F: opt-in supervised incremental job runner.

Single queue reservation, staging prepared under approved job, periodical
heartbeat and exact fenced release. No public generation publication or
unattended retry. May be called by a future scheduler only with explicit
job-specific execution confirmation.
"""
from __future__ import annotations

from pathlib import Path

from rag.runtime.auto_index_supervisor import (
    reserve_index_supervisor, release_index_supervisor,
)
from rag.runtime.auto_index_staging import prepare_auto_staging
from rag.runtime.auto_index_worker import _begin_batch
from rag.runtime.auto_index_checkpoint import update_auto_checkpoint
from rag.runtime.auto_index_batch import inventory_auto_vectors
from rag.runtime.production_publish import validate_staged_index
from rag.runtime.auto_index_queue import get_job
from rag.runtime.auto_index_incremental_fenced import execute_fenced_incremental_batch
from rag.runtime.auto_index_worker import _public_generation, _free_ram_mib
from rag.models.backend_policy import TEXT_MODEL_REVISION
from rag.models.code_backend_policy import CODE_MODEL_REVISION


def run_supervised_incremental_batch(
    queue_path: Path, baseline_job_id: str, candidate_job_id: str, *,
    execute: bool = False, operator_approved: bool = False,
    confirmation: str | None = None, max_vectors: int = 256,
    batch_index: int = 0,
    **model_revisions: str,
) -> dict:
    if (execute is not True or operator_approved is not True
            or confirmation != "RAG_AUTO_INCREMENTAL_RUN:" + candidate_job_id):
        raise PermissionError("explicit candidate-specific incremental authorization required")
    if type(batch_index) is not int or batch_index < 0:
        raise ValueError("nonnegative integer batch_index required")
    if type(max_vectors) is not int or not 1 <= max_vectors <= 256:
        raise ValueError("max_vectors must be from 1 to 256")
    expected_versions = {
        "baseline_text_model": TEXT_MODEL_REVISION,
        "candidate_text_model": TEXT_MODEL_REVISION,
        "baseline_code_model": CODE_MODEL_REVISION,
        "candidate_code_model": CODE_MODEL_REVISION,
    }
    if model_revisions != expected_versions:
        raise PermissionError("incremental execution must match installed pinned models")
    if _free_ram_mib() < 1600:
        return {
            "state":"WAITING_FOR_MEMORY",
            "minimum_free_mib":1600,
            "worker_started":False,
            "public_pointer_updated":False,
        }
    initial_public = _public_generation()
    lease = reserve_index_supervisor(
        queue_path, candidate_job_id, operator_approved=True,
        reservation_enabled=True, lease_seconds=3600,
    )
    if lease.get("state") == "SUPERVISOR_BUSY":
        return {**lease, "worker_started":False,"public_pointer_updated":False}
    if lease.get("state") != "RESERVED_NO_WORKER":
        raise RuntimeError("supervisor did not provide an exclusive reservation")
    token, generation=lease["lease_token"], lease["generation"]
    succeeded = False
    try:
        prepare_auto_staging(
            queue_path, candidate_job_id, operator_approved=True,
            preparation_enabled=True,
        )
        if _public_generation() != initial_public:
            raise RuntimeError("public generation changed before import")
        result=execute_fenced_incremental_batch(
            queue_path, baseline_job_id, candidate_job_id,
            lease_token=token, generation=generation,
            operator_approved=True, max_vectors=max_vectors,
            batch_index=batch_index, **model_revisions,
        )
        if _public_generation() != initial_public:
            raise RuntimeError("public generation changed during import; stage requires audit")
        stage_state=inventory_auto_vectors(queue_path,candidate_job_id)
        validated=False
        if stage_state["complete"]:
            from rag.runtime.auto_index_approval import read_reviewed_sources,revalidate_auto_index_preview
            job=get_job(queue_path,candidate_job_id)
            reviewed=read_reviewed_sources(queue_path,candidate_job_id)
            revalidate_auto_index_preview({
                "schema_version":1,"project_id":job["project_id"],
                "source_root":job["source_root"],"scope":job["requested_scope"],
                "sources":reviewed["sources"],"review_sha256":reviewed["review_sha256"],
            })
            check=validate_staged_index(stage_state["stage"],job["project_id"])
            if (check["chunks"]!=stage_state["chunks"]
                    or check["text_vectors"]!=stage_state["text_done"]
                    or check["code_vectors"]!=stage_state["code_done"]):
                raise RuntimeError("staged Qdrant validation differs from inventory")
            validated=True
        # Transition to RUNNING only after the already verified vector import.
        # Both operations enforce the same lease token and generation.
        _begin_batch(queue_path,candidate_job_id,token,generation)
        try:
            reconciled=update_auto_checkpoint(
                queue_path,candidate_job_id,token,generation,
                validated=validated,last="INCREMENTAL_REUSED",
            )
        except Exception as exc:
            try:
                update_auto_checkpoint(
                    queue_path,candidate_job_id,token,generation,
                    failure=type(exc).__name__,last="FAILED",
                )
            except Exception:
                # A stale worker must not override another supervisor owner.
                pass
            raise
        succeeded = True
        return {
            **result,**reconciled,"public_generation_unchanged":initial_public,
            "supervisor_release_expected":True,
            "generation_activated":False,"public_pointer_updated":False,
        }
    finally:
        # The fencing store will reject a stale or foreign lease owner.
        released = release_index_supervisor(
            queue_path, candidate_job_id, token, generation,
        )
        if succeeded and released.get("accepted") is not True:
            raise RuntimeError("supervisor release not confirmed after incremental batch")
