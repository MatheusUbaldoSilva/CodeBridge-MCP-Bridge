"""RAG-AUTO-02.5: explicitly launch one isolated indexing process.

The launcher returns PROCESS_STARTED, never claims embeddings completed. The
child is bounded, logs locally and polls the persistent pause/cancel state.
No shell interpolation, external repositories or public index publication.
"""
from __future__ import annotations

from datetime import datetime,timezone
import os
from pathlib import Path
import subprocess
import sys

from rag.runtime.auto_index_queue import (
    _canonical_queue_path, AutoIndexQueueError,get_job,
)
from rag.runtime.auto_index_supervisor import validate_job_sources
from rag.runtime.auto_index_worker import _free_ram_mib


def _trusted_runtime_python() -> Path:
    python=Path.home()/"CodeBridge-Runtime"/"dev"/"Scripts"/"python.exe"
    if not python.is_file() or python.is_symlink():
        raise AutoIndexQueueError("trusted CodeBridge DEV Python unavailable")
    return python.resolve(strict=True)


def launch_approved_auto_job(
    queue_path: Path, job_id: str, *,execute: bool=False,
    operator_approved: bool=False,confirmation: str|None=None,
    batch_size: int=256,max_batches: int=96,
    python_executable: Path|None=None,popen_factory=None,
) -> dict:
    """Start only on a deliberate operator action; never runs on app startup."""
    if execute is not True or operator_approved is not True or (
        confirmation!="RAG_AUTO_LAUNCH:"+job_id
    ):
        raise PermissionError("explicit launch confirmation required")
    if type(batch_size) is not int or not 1<=batch_size<=256:
        raise ValueError("invalid batch size")
    if type(max_batches) is not int or not 1<=max_batches<=10000:
        raise ValueError("invalid maximum batches")
    queue=_canonical_queue_path(queue_path)
    job=get_job(queue,job_id)
    if job is None or not job["approved"] or job["state"]!="QUEUED":
        raise AutoIndexQueueError("only approved QUEUED jobs can start")
    validate_job_sources(queue,job_id)
    if _free_ram_mib()<1600:
        return {"state":"WAITING_FOR_MEMORY","job_id":job_id,
                "minimum_free_mib":1600,"process_started":False}
    root=Path(__file__).resolve().parents[2]
    if not (root/"rag"/"runtime"/"auto_index_runner.py").is_file():
        raise AutoIndexQueueError("DEV auto-index runner source missing")
    python=(_trusted_runtime_python() if python_executable is None
            else Path(python_executable).resolve(strict=True))
    if not python.is_file():
        raise AutoIndexQueueError("Python interpreter unavailable")
    logs=queue.parent.parent/"logs"
    if logs.is_symlink():
        raise AutoIndexQueueError("log path cannot be a symlink")
    logs.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    logfile=logs/f"{job_id}-{stamp}.log"
    command=[
        str(python),"-u","-m","rag.runtime.auto_index_runner",
        "--queue-path",str(queue),"--job-id",job_id,"--execute",
        "--operator-approved","--confirmation","RAG_AUTO_RUN:"+job_id,
        "--batch-size",str(batch_size),"--max-batches",str(max_batches),
    ]
    keep=("PATH","SYSTEMROOT","WINDIR","TEMP","TMP","USERPROFILE",
          "LOCALAPPDATA","APPDATA","HOMEDRIVE","HOMEPATH",
          "CUDA_VISIBLE_DEVICES","CUDA_PATH")
    environment={key:value for key,value in os.environ.items() if key.upper() in keep}
    environment["PYTHONPATH"]=str(root)
    environment["PYTHONDONTWRITEBYTECODE"]="1"
    environment["PYTHONUNBUFFERED"]="1"
    flags=(getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0)
           | getattr(subprocess,"CREATE_NO_WINDOW",0))
    spawn=subprocess.Popen if popen_factory is None else popen_factory
    try:
        with logfile.open("xb") as output:
            child=spawn(
                command,cwd=str(root),env=environment,
                stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,
                close_fds=True,creationflags=flags,
            )
    except BaseException:
        logfile.unlink(missing_ok=True)
        raise
    return {
        "job_id":job_id,"state":"PROCESS_STARTED_UNVERIFIED",
        "pid":int(child.pid),"log_path":str(logfile),
        "process_started":True,
        "index_published":False,"public_generation_changed":False,
    }
