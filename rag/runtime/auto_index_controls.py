"""RAG-AUTO-01.5: durable user control requests for auto RAG jobs.

Only changes requested queue state. Future execution must honor these states at
a safe batch boundary; no subprocess, model or production pointer is touched.
"""
from __future__ import annotations

from contextlib import closing
import json
import math
from pathlib import Path
import sqlite3
import time
from typing import Literal

from rag.runtime.auto_index_queue import (
    _canonical_queue_path, AutoIndexQueueError,
    get_job,
)
Action = Literal["PAUSE","RESUME","CANCEL"]

_ALLOWED: dict[str,dict[str,str]] = {
    "PAUSE":{
        "QUEUED":"PAUSED",
        "RUNNING":"PAUSE_REQUESTED",
    },
    "RESUME":{
        "PAUSED":"QUEUED",
    },
    "CANCEL":{
        "DRAFT":"CANCELLED",
        "AWAITING_APPROVAL":"CANCELLED",
        "QUEUED":"CANCELLED",
        "PAUSED":"CANCELLED",
        "RUNNING":"CANCEL_REQUESTED",
        "PAUSE_REQUESTED":"CANCEL_REQUESTED",
    },
}


def request_auto_index_control(
    queue_path: Path,job_id: str,action: Action, *,
    operator_requested: bool=False,control_enabled: bool=False,
    now_epoch: float | None=None,
) -> dict:
    """Record a control request with an auditable atomic transition."""
    if operator_requested is not True or control_enabled is not True:
        raise PermissionError("explicit operator control request required")
    if action not in _ALLOWED:
        raise ValueError("unknown control action")
    job=get_job(queue_path,job_id)
    if job is None:
        raise AutoIndexQueueError("job not found")
    if job["state"] not in _ALLOWED[action]:
        raise AutoIndexQueueError(f"cannot {action} in state {job['state']}")
    now=time.time() if now_epoch is None else now_epoch
    if type(now) not in (int,float) or not math.isfinite(now) or now<0:
        raise ValueError("invalid timestamp")
    # Validate frozen sources before putting a previously paused job back
    # into the queue. This still does not start a model.
    if action=="RESUME":
        receipt_needed=job["state"]=="PAUSED"
        if receipt_needed:
            # Temporarily model queued status for validation, without
            # modifying persisted state before validation succeeds.
            from rag.runtime.auto_index_approval import (
                read_reviewed_sources,revalidate_auto_index_preview,
            )
            receipt=read_reviewed_sources(queue_path,job_id)
            revalidate_auto_index_preview({
                "schema_version":1,
                "project_id":job["project_id"],
                "source_root":job["source_root"],
                "scope":job["requested_scope"],
                "sources":receipt["sources"],
                "review_sha256":receipt["review_sha256"],
            })
    path=_canonical_queue_path(queue_path)
    if not path.is_file():
        raise AutoIndexQueueError("queue is missing")
    with closing(sqlite3.connect(
        path.as_uri()+"?mode=rw",uri=True,timeout=12,isolation_level=None,
    )) as cn:
        cn.execute("PRAGMA foreign_keys=ON")
        cn.execute("PRAGMA busy_timeout=12000")
        cn.execute("BEGIN IMMEDIATE")
        try:
            current=cn.execute(
                "SELECT state,approved FROM auto_jobs WHERE job_id=?",(job_id,),
            ).fetchone()
            if current is None or current[0] not in _ALLOWED[action]:
                raise AutoIndexQueueError("job state changed before control was applied")
            if action=="RESUME":
                if current[1]!=1:
                    raise PermissionError("unapproved job cannot resume")
                from rag.runtime.auto_index_approval import (
                    read_reviewed_sources,revalidate_auto_index_preview,
                )
                # Recheck again under the queue write transaction.
                receipt=read_reviewed_sources(queue_path,job_id)
                revalidate_auto_index_preview({
                    "schema_version":1,
                    "project_id":job["project_id"],
                    "source_root":job["source_root"],
                    "scope":job["requested_scope"],
                    "sources":receipt["sources"],
                    "review_sha256":receipt["review_sha256"],
                })
            after=_ALLOWED[action][current[0]]
            cn.execute(
                "UPDATE auto_jobs SET state=?,updated_at_epoch=? WHERE job_id=?",
                (after,now,job_id),
            )
            # Cancel queued/paused/draft jobs or pause queued jobs safely:
            # remove their unstarted reservations and fence stale owners.
            if after in ("CANCELLED","PAUSED"):
                present=cn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name='auto_worker_lease'"
                ).fetchone()
                if present:
                    cn.execute(
                        "UPDATE auto_worker_lease SET job_id=NULL,"
                        "lease_token=NULL,lease_until_epoch=NULL,"
                        "generation=generation+1,updated_at_epoch=? "
                        "WHERE singleton=1 AND job_id=?",
                        (now,job_id),
                    )
            cn.execute(
                "INSERT INTO auto_job_events(job_id,event_type,recorded_at_epoch,details_json) "
                "VALUES(?,?,?,?)",
                (job_id,"CONTROL_"+action,now,json.dumps({
                    "previous_state":current[0],"state":after,
                    "execution_started":False,
                    "publication_authorized":False,
                },sort_keys=True)),
            )
            cn.execute("COMMIT")
        except BaseException:
            if cn.in_transaction:
                cn.execute("ROLLBACK")
            raise
    return {
        "job_id":job_id,"state":after,"accepted":True,
        "worker_started":False,"publication_authorized":False,
        "stopped_at_safe_boundary":after in ("PAUSED","CANCELLED"),
        "requires_worker_ack":after in ("PAUSE_REQUESTED","CANCEL_REQUESTED"),
    }
