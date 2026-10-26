"""RAG-AUTO-03 protected production-facing entry points.

Only the project-level read-only catalog is eligible; never mutate the public
generation pointer or overwrite a preexisting project. Used by GUI/MCP after
explicit operator action, with all real paths resolved from local configuration.
"""
from __future__ import annotations

import os
from pathlib import Path

from rag.runtime.auto_index_queue import default_queue_path,get_job
from rag.runtime.auto_index_generation import (
    prepare_verified_auto_generation,verify_prepared_auto_generation,
)
from rag.runtime.auto_index_canary import (
    activate_auto_canary,rollback_auto_canary,
)
from rag.runtime.isolated_project_index import catalog_path,_workspace_root


def _identity(job_id: str) -> str:
    job=get_job(default_queue_path(),job_id)
    if job is None or job["project_id"]=="codebridge":
        raise PermissionError("unregistered or public index job is not eligible")
    return job["project_id"]


def _paths() -> tuple[Path,Path,Path,Path]:
    catalog=catalog_path()
    pointer=catalog.parent/"active-generation.json"
    workspace=_workspace_root()
    home=os.environ.get("USERPROFILE")
    if not home:
        raise RuntimeError("USERPROFILE missing")
    runtime=Path(home)/"CodeBridge-Runtime"/"dev"/"Scripts"/"python.exe"
    if not pointer.is_file():
        raise RuntimeError("public generation pointer unavailable")
    if not runtime.is_file():
        raise RuntimeError("approved DEV Python not installed")
    return catalog,pointer,workspace,runtime


def prepare_auto_candidate(
    job_id: str,*,execute: bool=False,operator_approved: bool=False,
    confirmation: str|None=None,
) -> dict:
    project=_identity(job_id)
    if (execute is not True or operator_approved is not True
            or confirmation!="RAG_AUTO_PREPARE:"+project+":"+job_id):
        raise PermissionError("explicit candidate preparation consent required")
    return prepare_verified_auto_generation(
        default_queue_path(),job_id,operator_approved=True,prepare_enabled=True,
    )


def enable_auto_canary(
    job_id: str,*,execute: bool=False,operator_approved: bool=False,
    confirmation: str|None=None,
) -> dict:
    project=_identity(job_id)
    if (execute is not True or operator_approved is not True
            or confirmation!="RAG_AUTO_CANARY:"+project+":"+job_id):
        raise PermissionError("explicit project canary consent required")
    catalog,pointer,workspace,runtime=_paths()
    return activate_auto_canary(
        default_queue_path(),job_id,catalog_file=catalog,
        public_pointer=pointer,workspace=workspace,
        python_executable=runtime,operator_approved=True,
        confirmation=confirmation,
    )


def disable_auto_canary(
    job_id: str,*,execute: bool=False,operator_approved: bool=False,
    confirmation: str|None=None,
) -> dict:
    _identity(job_id)
    if (execute is not True or operator_approved is not True
            or confirmation!="RAG_AUTO_CANARY_ROLLBACK:"+job_id):
        raise PermissionError("explicit rollback approval required")
    catalog,pointer,workspace,_runtime=_paths()
    return rollback_auto_canary(
        job_id,catalog_file=catalog,public_pointer=pointer,
        workspace=workspace,operator_approved=True,confirmation=confirmation,
    )


def auto_canary_status(job_id: str) -> dict:
    project=_identity(job_id)
    candidate=None
    try:
        from rag.runtime.auto_index_generation import _paths as paths
        generation,snapshot=paths(default_queue_path(),job_id,project)
        if generation.is_dir() and snapshot.is_dir():
            candidate={"prepared":True,"generation":str(generation)}
        else:
            candidate={"prepared":False}
    except OSError:
        candidate={"prepared":False}
    catalog=catalog_path()
    record=None
    if catalog.is_file():
        import json
        data=json.loads(catalog.read_text(encoding="utf-8-sig"))
        if data.get("schema_version")!=1 or not isinstance(data.get("projects"),dict):
            raise RuntimeError("catalog schema invalid")
        record=data["projects"].get(project)
    return {
        "job_id":job_id,"project_id":project,
        "candidate":candidate,
        "state":("CANARY_ACTIVE" if isinstance(record,dict)
                 and record.get("enabled") is True
                 and record.get("job_id")==job_id
                 and record.get("index_family")=="RAG_AUTO_03"
                 else "PREPARED_NOT_REGISTERED" if candidate["prepared"]
                 else "NOT_PREPARED"),
        "public_generation_changed":False,
    }
