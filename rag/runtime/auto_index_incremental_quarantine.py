"""RAG-AUTO-05-F: non-destructive isolated-stage quarantine.

Explicit operator action only. Refuses live or unverified ownership,
renames the stage inside the same isolated workspace without deleting data.
Never mutates public RAG generation or Git.
"""
from __future__ import annotations

from pathlib import Path
import os
import time
import uuid

from rag.runtime.auto_index_queue import get_job
from rag.runtime.auto_index_staging import stage_directory
from rag.runtime.auto_index_supervisor import inspect_index_supervisor
from rag.runtime.production_generation_lock import production_generation_lock


def quarantine_interrupted_incremental_stage(
    queue_path: Path, job_id: str, *,
    operator_approved: bool = False,
    confirmation: str | None = None,
) -> dict:
    if operator_approved is not True or confirmation != "RAG_AUTO_QUARANTINE:"+job_id:
        raise PermissionError("explicit job-specific quarantine confirmation required")
    job=get_job(queue_path,job_id)
    if job is None or not job.get("approved") or job.get("project_id")=="codebridge":
        raise PermissionError("approved private project required")
    if job.get("state") not in ("PAUSED","FAILED","CANCELLED"):
        raise PermissionError("only stopped/failed job stages may be quarantined")
    lease=inspect_index_supervisor(queue_path)
    # An expired reservation is NOT evidence that its worker exited. Require
    # explicit unreserved state to avoid moving open SQLite/Qdrant stores.
    if lease.get("state") != "NOT_RESERVED":
        raise PermissionError("supervisor must be demonstrably unreserved")
    stage=stage_directory(queue_path,job_id)
    if (not stage.is_dir() or stage.is_symlink()
            or (hasattr(stage,"is_junction") and stage.is_junction())):
        raise ValueError("stage missing or redirected")
    destination=stage.parent/("quarantine-"+job_id+"-"+uuid.uuid4().hex)
    if (destination.exists() or destination.is_symlink() or
            (hasattr(destination,"is_junction") and destination.is_junction())):
        raise ValueError("quarantine destination already exists")
    with production_generation_lock(exclusive=True,channel="semantic"):
        # The first read is an early refusal. A second read under the
        # semantic lock prevents relocation after ownership changes.
        fresh=inspect_index_supervisor(queue_path)
        if fresh.get("state") != "NOT_RESERVED":
            raise PermissionError("supervisor became reserved during quarantine")
        current=get_job(queue_path,job_id)
        if (current is None or current.get("approved") is not True
                or current.get("project_id") != job["project_id"]
                or current.get("state") not in ("PAUSED","FAILED","CANCELLED")):
            raise PermissionError("candidate job changed during quarantine")
        if not stage.is_dir() or stage.is_symlink() or (
            hasattr(stage,"is_junction") and stage.is_junction()
        ):
            raise PermissionError("candidate stage changed during quarantine")
        os.replace(stage,destination)
    return {
        "mode":"ISOLATED_STAGE_QUARANTINED",
        "job_id":job_id,
        "quarantine_path":str(destination),
        "recoverable_data_preserved":True,
        "worker_started":False,
        "vectors_deleted":False,
        "generation_activated":False,
        "public_pointer_updated":False,
        "operator_audit_required":True,
    }
