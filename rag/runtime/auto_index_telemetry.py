"""RAG-AUTO-01.6 read-only, honest telemetry for an auto-index job.

No fake vector progress, model load, indexing or queue mutation. GPU probing
is optional and bounded; consumers must run it off the Qt main thread.
"""
from __future__ import annotations

import math
from pathlib import Path
import shutil
import subprocess
import time

from rag.runtime.auto_index_queue import get_job, inspect_queue, list_events
from rag.runtime.auto_index_supervisor import inspect_index_supervisor

_GPU_COMMAND=("nvidia-smi","--query-gpu=memory.used,memory.total,utilization.gpu",
              "--format=csv,noheader,nounits")


def read_auto_index_job_status(
    queue_path: Path, job_id: str, *, probe_resources: bool=False,
) -> dict:
    """Produce truthful UI fields strictly from SQLite and optional resources."""
    job=get_job(queue_path,job_id)
    if job is None:
        raise ValueError("auto-index job not found")
    done=job["text_vectors_done"]+job["code_vectors_done"]
    expected=job["chunk_count"]
    percent=round(100*done/expected,2) if expected else None
    if expected and not 0<=done<=expected:
        raise ValueError("persisted progress outside allowed range")
    if job["state"]=="READY_FOR_REVIEW" and (expected==0 or done!=expected):
        raise ValueError("ready job lacks complete vector totals")
    events=list_events(queue_path,job_id)
    lease=inspect_index_supervisor(queue_path)
    owns_lease=(lease.get("state")=="LEASE_RECORDED" and lease.get("job_id")==job_id)
    result={
        "job_id":job_id,
        "project_id":job["project_id"],
        "state":job["state"],
        "file_count":job["file_count"],
        "chunk_count":expected,
        "vectors_done":done,
        "vectors_expected":expected,
        "text_vectors_done":job["text_vectors_done"],
        "code_vectors_done":job["code_vectors_done"],
        "percent":percent,
        "percent_known":percent is not None,
        "progress_basis":"PERSISTED_SQLITE_COUNTERS",
        "candidate_generation":job["candidate_generation"],
        "reviewed":bool(job["approved"]),
        "last_error":job["last_error"],
        "last_event":events[-1]["event_type"] if events else None,
        "supervisor_reserved":owns_lease,
        "worker_started_by_status_read":False,
        "publication_authorized":False,
        "memory":None,"gpu":None,
    }
    if probe_resources:
        result["memory"],result["gpu"]=_probe_system_resources()
    return result


def _probe_system_resources() -> tuple[dict | None,dict | None]:
    memory=None
    try:
        import psutil
        usage=psutil.virtual_memory()
        memory={
            "free_mib":int(usage.available // (1024**2)),
            "total_mib":int(usage.total // (1024**2)),
            "safe_to_start_batch":usage.available>=1600*(1024**2),
        }
    except (ImportError,OSError,ValueError):
        pass
    gpu=None
    try:
        completed=subprocess.run(
            _GPU_COMMAND,capture_output=True,text=True,check=False,timeout=3,
            shell=False,
        )
        if completed.returncode==0:
            first=completed.stdout.strip().splitlines()[0]
            values=[part.strip() for part in first.split(",")]
            if len(values)==3:
                used,total,utilization=[int(item) for item in values]
                if total>0 and 0<=used<=total and 0<=utilization<=100:
                    gpu={
                        "used_mib":used,"total_mib":total,
                        "utilization_percent":utilization,
                    }
    except (OSError,IndexError,TypeError,ValueError,subprocess.TimeoutExpired):
        pass
    return memory,gpu


def inspect_auto_index_dashboard(
    queue_path: Path, *, project_id: str | None=None, limit: int=50,
) -> dict:
    from rag.runtime.auto_index_queue import list_jobs
    jobs=list_jobs(queue_path,project_id=project_id,limit=limit)
    return {
        "queue":inspect_queue(queue_path),
        "jobs":[{
            "job_id":job["job_id"],"project_id":job["project_id"],
            "state":job["state"],"file_count":job["file_count"],
            "vectors_done":job["text_vectors_done"]+job["code_vectors_done"],
            "vectors_expected":job["chunk_count"],
            "updated_at_epoch":job["updated_at_epoch"],
        } for job in jobs],
        "models_started":False,"index_published":False,
    }
