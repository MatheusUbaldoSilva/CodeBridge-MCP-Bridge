"""RAG-AUTO-02.4: fenced persistence at safe vector-batch boundaries.

The truth is Qdrant (validated against SQLite). Job totals are durable
projections. A stale lease token can never accept a new checkpoint.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import sqlite3
import time

from rag.runtime.auto_index_queue import (
    _canonical_queue_path,AutoIndexQueueError,get_job,
)
from rag.runtime.auto_index_batch import inventory_auto_vectors
from rag.runtime.auto_index_staging import stage_directory


def _require_owner(cn: sqlite3.Connection,job_id: str,token: str,
                   generation: int,now: float) -> None:
    owner=cn.execute(
        "SELECT job_id,lease_token,generation,lease_until_epoch "
        "FROM auto_worker_lease WHERE singleton=1",
    ).fetchone()
    if (owner is None or owner[0]!=job_id or owner[1]!=token
            or owner[2]!=generation or owner[3] is None or owner[3]<=now):
        raise AutoIndexQueueError("stale supervisor cannot modify job progress")


def _persist_stage_progress(stage: Path,job_id: str,status: dict,last: str) -> None:
    path=stage/"progress.json"
    payload=json.loads(path.read_text(encoding="utf-8"))
    if (payload.get("job_id")!=job_id or
            payload.get("expected_chunks")!=status["chunks"] or
            payload.get("published") is not False):
        raise AutoIndexQueueError("progress receipt does not match stage")
    payload.update({
        "text_vectors_done":status["text_done"],
        "code_vectors_done":status["code_done"],
        "total_vectors_done":status["total_done"],
        "last_batch_result":last,
        "last_updated_at":datetime.now(timezone.utc).isoformat(),
    })
    temp=path.with_name("progress.json.tmp")
    if temp.exists():
        raise AutoIndexQueueError("stale progress temp file must be audited")
    try:
        temp.write_text(json.dumps(payload,sort_keys=True,indent=2)+"\n",encoding="utf-8")
        os.replace(temp,path)
    finally:
        temp.unlink(missing_ok=True)


def update_auto_checkpoint(
    queue_path: Path,job_id: str,lease_token: str,generation: int, *,
    validated: bool=False,now_epoch: float|None=None,last: str="PASS",
    failure: str|None=None,
) -> dict:
    if not isinstance(lease_token,str) or len(lease_token)!=32:
        raise ValueError("invalid lease token")
    now=time.time() if now_epoch is None else now_epoch
    status=inventory_auto_vectors(queue_path,job_id)
    if status["complete"] and not validated:
        # Only a full independent validator may mark a staged job READY.
        next_state="VALIDATING"
    else:
        next_state="READY_FOR_REVIEW" if validated else "QUEUED"
    if validated and not status["complete"]:
        raise AutoIndexQueueError("cannot validate incomplete vectors")
    if failure is not None:
        if not isinstance(failure,str) or not failure or len(failure)>128:
            raise ValueError("invalid failure classification")
        next_state="PAUSED"
    path=_canonical_queue_path(queue_path)
    with closing(sqlite3.connect(
        path.as_uri()+"?mode=rw",uri=True,timeout=12,isolation_level=None,
    )) as cn:
        cn.execute("PRAGMA busy_timeout=12000")
        cn.execute("BEGIN IMMEDIATE")
        try:
            _require_owner(cn,job_id,lease_token,generation,now)
            row=cn.execute(
                "SELECT state,approved FROM auto_jobs WHERE job_id=?",(job_id,),
            ).fetchone()
            if row is None or not row[1] or row[0] not in (
                "RUNNING","PAUSE_REQUESTED","CANCEL_REQUESTED","VALIDATING",
            ):
                raise AutoIndexQueueError("job cannot checkpoint in this state")
            state=row[0]
            if state=="PAUSE_REQUESTED":
                next_state="PAUSED"
            elif state=="CANCEL_REQUESTED":
                next_state="CANCELLED"
            # Stop before publication. State READY_FOR_REVIEW is never public.
            cn.execute(
                "UPDATE auto_jobs SET state=?,chunk_count=?,file_count=?,"
                "text_vectors_done=?,code_vectors_done=?,candidate_generation=?,"
                "last_error=?,updated_at_epoch=? WHERE job_id=?",
                (next_state,status["chunks"],status["documents"],
                 status["text_done"],status["code_done"],status["stage"],
                 failure,now,job_id),
            )
            cn.execute(
                "INSERT INTO auto_job_events(job_id,event_type,recorded_at_epoch,details_json) "
                "VALUES(?,?,?,?)",
                (job_id,"VECTORS_RECONCILED",now,json.dumps({
                    "text_done":status["text_done"],
                    "code_done":status["code_done"],
                    "expected":status["chunks"],
                    "state":next_state,"validated":validated,
                    "failure":failure,"published":False,
                },sort_keys=True)),
            )
            cn.execute("COMMIT")
        except BaseException:
            if cn.in_transaction:
                cn.execute("ROLLBACK")
            raise
    _persist_stage_progress(
        Path(status["stage"]),job_id,status,("FAILED_"+failure) if failure else (
            last if not validated else "COMPLETE"
        ),
    )
    return {
        "job_id":job_id,"state":next_state,
        "vectors_done":status["total_done"],
        "vectors_expected":status["chunks"],
        "text_vectors_done":status["text_done"],
        "code_vectors_done":status["code_done"],
        "index_published":False,"source":"QDRANT_VERIFIED",
    }


def _recover_orphaned_auto_job_with_guard(
    queue_path: Path,job_id: str, *,operator_approved: bool=False,
    now_epoch: float|None=None,
) -> dict:
    """Reset crashed RUNNING jobs only after lease expiry and source re-review.

    The caller must also hold the shared semantic model lock, preventing an
    old model process from writing vectors while a recovery executes.
    """
    if operator_approved is not True:
        raise PermissionError("operator recovery approval required")
    from rag.runtime.auto_index_approval import (
        read_reviewed_sources,revalidate_auto_index_preview,
    )
    job=get_job(queue_path,job_id)
    if job is None or job["state"]!="RUNNING" or not job["approved"]:
        raise AutoIndexQueueError("only orphaned RUNNING jobs can recover")
    receipt=read_reviewed_sources(queue_path,job_id)
    revalidate_auto_index_preview({
        "schema_version":1,"project_id":job["project_id"],
        "source_root":job["source_root"],"scope":job["requested_scope"],
        "sources":receipt["sources"],"review_sha256":receipt["review_sha256"],
    })
    now=time.time() if now_epoch is None else now_epoch
    status=inventory_auto_vectors(queue_path,job_id)
    with closing(sqlite3.connect(
        _canonical_queue_path(queue_path).as_uri()+"?mode=rw",
        uri=True,timeout=12,isolation_level=None,
    )) as cn:
        cn.execute("BEGIN IMMEDIATE")
        try:
            owner=cn.execute(
                "SELECT lease_until_epoch FROM auto_worker_lease WHERE singleton=1"
            ).fetchone()
            state=cn.execute("SELECT state FROM auto_jobs WHERE job_id=?",(job_id,)).fetchone()
            if (not owner or (owner[0] is not None and owner[0]>now)
                    or state!=("RUNNING",)):
                raise AutoIndexQueueError("job is active or lease not expired")
            cn.execute(
                "UPDATE auto_worker_lease SET job_id=NULL,lease_token=NULL,"
                "lease_until_epoch=NULL,generation=generation+1,updated_at_epoch=? "
                "WHERE singleton=1",(now,),
            )
            cn.execute(
                "UPDATE auto_jobs SET state='QUEUED',file_count=?,chunk_count=?,"
                "text_vectors_done=?,code_vectors_done=?,candidate_generation=?,"
                "updated_at_epoch=? WHERE job_id=?",
                (status["documents"],status["chunks"],status["text_done"],
                 status["code_done"],status["stage"],now,job_id),
            )
            cn.execute(
                "INSERT INTO auto_job_events(job_id,event_type,recorded_at_epoch,details_json) "
                "VALUES(?,?,?,?)",(job_id,"ORPHAN_RECOVERED",now,json.dumps({
                    "vectors_done":status["total_done"],"state":"QUEUED",
                })),
            )
            cn.execute("COMMIT")
        except BaseException:
            if cn.in_transaction:
                cn.execute("ROLLBACK")
            raise
    _persist_stage_progress(Path(status["stage"]),job_id,status,"RECOVERED")
    return {"state":"QUEUED","vectors_done":status["total_done"],
            "index_published":False}

def recover_orphaned_auto_job(
    queue_path: Path,job_id: str, *,operator_approved: bool=False,
    now_epoch: float|None=None,semantic_guard_factory=None,
) -> dict:
    """Recover only while holding the shared cross-process model lock."""
    if operator_approved is not True:
        raise PermissionError("operator recovery approval required")
    if semantic_guard_factory is None:
        from rag.runtime.production_generation_lock import production_generation_lock
        semantic_guard_factory=lambda:production_generation_lock(
            exclusive=True,channel="semantic",
        )
    with semantic_guard_factory():
        return _recover_orphaned_auto_job_with_guard(
            queue_path,job_id,operator_approved=True,now_epoch=now_epoch,
        )
