"""RAG-AUTO-01.8: explicit API boundary shared by DEV UI and MCP.

No imports have side effects; preview/status are read-only. Mutations require
literal operator confirmation and never spawn an indexing worker or publish.
"""
from __future__ import annotations

from pathlib import Path

from rag.runtime.auto_index_approval import (
    approve_auto_index_draft, build_auto_index_preview,
)
from rag.runtime.auto_index_controls import request_auto_index_control
from rag.runtime.auto_index_queue import (
    create_draft, default_queue_path, get_job,
)
from rag.runtime.auto_index_telemetry import (
    inspect_auto_index_dashboard, read_auto_index_job_status,
)


def auto_preview(project_id: str, source_root: str, *,
                 scope: str="BOTH",paths: list[str] | None=None) -> dict:
    return build_auto_index_preview(
        project_id,source_root,scope=scope,paths=paths or (),
    )


def auto_approve(
    project_id: str,source_root: str, *,scope: str="BOTH",
    paths: list[str] | None=None,confirmed_digest: str,
    operator_approved: bool=False,execute: bool=False,
    confirmation: str | None=None,
    queue_path: Path | None=None,
) -> dict:
    """Explicit consent binds the immutable file list before any new DB write."""
    if project_id=="codebridge":
        raise PermissionError(
            "public codebridge namespace is reserved; choose a distinct isolated project"
        )
    if (execute is not True or operator_approved is not True
            or confirmation != "RAG_AUTO_QUEUE:"+project_id+":"+confirmed_digest):
        raise PermissionError("explicit project+SHA approval required")
    preview=auto_preview(project_id,source_root,scope=scope,paths=paths)
    if preview["review_sha256"]!=confirmed_digest:
        raise ValueError("source snapshot differs from operator confirmation")
    path=default_queue_path() if queue_path is None else queue_path
    job=create_draft(
        path,project_id=project_id,source_root=preview["source_root"],
        scope=scope,idempotency_key="auto-"+confirmed_digest,
        allow_write=True,
    )
    if job["state"]!="DRAFT":
        if job["state"] in ("QUEUED","PAUSED") and job["approved"]:
            return {
                "state":job["state"],"job_id":job["job_id"],
                "reused":True,"review_sha256":confirmed_digest,
                "worker_started":False,"publication_authorized":False,
            }
        raise ValueError("existing request cannot be overwritten or restarted")
    approved=approve_auto_index_draft(
        path,job["job_id"],preview,
        confirmed_digest=confirmed_digest,operator_approved=True,allow_write=True,
    )
    return {**approved,"reused":False}


def auto_status(*,project_id: str | None=None,job_id: str | None=None,
                queue_path: Path | None=None) -> dict:
    path=default_queue_path() if queue_path is None else queue_path
    if job_id is not None:
        result=read_auto_index_job_status(path,job_id)
        if project_id is not None and result["project_id"]!=project_id:
            raise PermissionError("job belongs to a different project")
        return result
    return inspect_auto_index_dashboard(path,project_id=project_id)


def auto_control(
    job_id: str,action: str, *,execute: bool=False,
    operator_approved: bool=False,confirmation: str | None=None,
    queue_path: Path | None=None,
) -> dict:
    if (execute is not True or operator_approved is not True
            or confirmation != "RAG_AUTO_CONTROL:"+job_id+":"+action):
        raise PermissionError("explicit job+action confirmation required")
    return request_auto_index_control(
        default_queue_path() if queue_path is None else queue_path,
        job_id,action,operator_requested=True,control_enabled=True,
    )
