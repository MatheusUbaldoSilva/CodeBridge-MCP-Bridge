"""RAG-AUTO-01.4 supervisor reservation lease for isolated index jobs.

Exclusive, fenced reservations only: NEVER launches Jina, executes a worker,
mutates the published RAG pointer, or advances any vector progress.
"""
from __future__ import annotations

from contextlib import closing
import math
from pathlib import Path
import sqlite3
import time
import uuid

from rag.runtime.auto_index_queue import (
    _canonical_queue_path, _connect, AutoIndexQueueError, get_job,
)
from rag.runtime.auto_index_approval import (
    build_auto_index_preview, read_reviewed_sources,
)

_LEASE_SQL = """CREATE TABLE IF NOT EXISTS auto_worker_lease (
    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
    job_id TEXT,
    lease_token TEXT,
    lease_until_epoch REAL,
    generation INTEGER NOT NULL CHECK(generation>=0),
    updated_at_epoch REAL NOT NULL
)"""


def _now(explicit: float | None) -> float:
    value=time.time() if explicit is None else explicit
    if type(value) not in (int,float) or not math.isfinite(value) or value<0:
        raise ValueError("invalid timestamp")
    return float(value)


def _seconds(value: float) -> float:
    if type(value) not in (int,float) or not math.isfinite(value) or not 10<=value<=3600:
        raise ValueError("lease time must be between 10 and 3600 seconds")
    return float(value)


def _ensure_lease_store(connection: sqlite3.Connection) -> None:
    connection.execute(_LEASE_SQL)
    connection.execute(
        "INSERT OR IGNORE INTO auto_worker_lease "
        "(singleton,job_id,lease_token,lease_until_epoch,generation,updated_at_epoch) "
        "VALUES(1,NULL,NULL,NULL,0,0)"
    )


def validate_job_sources(queue_path: Path, job_id: str) -> dict:
    """Recheck the complete original source receipt before any worker claim."""
    job=get_job(queue_path,job_id)
    if job is None or job["state"]!="QUEUED" or not job["approved"]:
        raise AutoIndexQueueError("job is not an approved queued index request")
    receipt=read_reviewed_sources(queue_path,job_id)
    paths=[source["path"] for source in receipt["sources"]]
    previous={
        "schema_version":1,
        "project_id":job["project_id"],
        "source_root":job["source_root"],
        "scope":job["requested_scope"],
        "sources":receipt["sources"],
        "review_sha256":receipt["review_sha256"],
    }
    from rag.runtime.auto_index_approval import revalidate_auto_index_preview
    current=revalidate_auto_index_preview(previous)
    if current["review_sha256"]!=receipt["review_sha256"]:
        raise AutoIndexQueueError("source receipt changed")
    return {
        "job_id":job_id,"project_id":job["project_id"],
        "files":len(paths),
        "source_revision":receipt["review_sha256"],
        "revalidated":True,
        "worker_started":False,
    }


def reserve_index_supervisor(
    queue_path: Path,job_id: str,*,operator_approved: bool=False,
    reservation_enabled: bool=False,lease_seconds: float=120,
    now_epoch: float | None=None,
) -> dict:
    """Reserve the *single* GPU/CPU worker slot without starting a worker."""
    if operator_approved is not True or reservation_enabled is not True:
        raise PermissionError("explicit reservation enable and approval required")
    seconds=_seconds(lease_seconds)
    now=_now(now_epoch)
    valid=validate_job_sources(queue_path,job_id)
    with closing(_connect(_canonical_queue_path(queue_path),create=True)) as cn:
        cn.execute("BEGIN IMMEDIATE")
        try:
            _ensure_lease_store(cn)
            row=cn.execute(
                "SELECT job_id,lease_token,lease_until_epoch,generation "
                "FROM auto_worker_lease WHERE singleton=1",
            ).fetchone()
            if row[1] is not None and row[2] is not None and row[2]>now:
                cn.execute("COMMIT")
                return {
                    "state":"SUPERVISOR_BUSY","owner_job_id":row[0],
                    "generation":row[3],"worker_started":False,
                    "publication_authorized":False,
                }
            checked=cn.execute(
                "SELECT state,approved FROM auto_jobs WHERE job_id=?",(job_id,),
            ).fetchone()
            if checked!=("QUEUED",1):
                raise AutoIndexQueueError("job state changed since source review")
            # Check the frozen source set while holding the reservation lock.
            validate_job_sources(queue_path,job_id)
            token=uuid.uuid4().hex
            new_generation=row[3]+1
            cn.execute(
                "UPDATE auto_worker_lease SET job_id=?,lease_token=?,"
                "lease_until_epoch=?,generation=?,updated_at_epoch=? "
                "WHERE singleton=1",
                (job_id,token,now+seconds,new_generation,now),
            )
            cn.execute("COMMIT")
        except BaseException:
            if cn.in_transaction:
                cn.execute("ROLLBACK")
            raise
    return {
        **valid,
        "state":"RESERVED_NO_WORKER",
        "lease_token":token,"generation":new_generation,
        "lease_until_epoch":now+seconds,"worker_started":False,
        "publication_authorized":False,
    }


def _change_lease(
    queue_path: Path,job_id: str,lease_token: str,generation: int,
    *,release: bool,now_epoch: float | None=None,lease_seconds: float=120,
) -> dict:
    now=_now(now_epoch)
    if not release:
        seconds=_seconds(lease_seconds)
    if (not isinstance(lease_token,str) or len(lease_token)!=32
            or type(generation) is not int or generation<=0):
        raise ValueError("invalid supervisor ownership")
    path=_canonical_queue_path(queue_path)
    if not path.is_file():
        return {"state":"SUPERVISOR_NOT_INITIALIZED","accepted":False}
    # This path needs a fenced writable transaction (the ordinary queue
    # reader uses query_only). Never create the store during a lease update.
    db=sqlite3.connect(path.as_uri()+"?mode=rw",uri=True,timeout=12,isolation_level=None)
    try:
        db.execute("PRAGMA busy_timeout=12000")
        db.execute("BEGIN IMMEDIATE")
        try:
            owner=db.execute(
                "SELECT job_id,lease_token,generation,lease_until_epoch "
                "FROM auto_worker_lease WHERE singleton=1",
            ).fetchone()
            if (owner is None or owner[0]!=job_id or owner[1]!=lease_token
                    or owner[2]!=generation or owner[3] is None or owner[3]<=now):
                db.execute("COMMIT")
                return {"state":"STALE_SUPERVISOR","accepted":False}
            expiry=None if release else now+seconds
            db.execute(
                "UPDATE auto_worker_lease SET job_id=?,lease_token=?,"
                "lease_until_epoch=?,updated_at_epoch=? WHERE singleton=1",
                (None if release else job_id,
                 None if release else lease_token,expiry,now),
            )
            db.execute("COMMIT")
            return {
                "state":"RELEASED" if release else "RENEWED",
                "accepted":True,"generation":generation,
                "lease_until_epoch":expiry,"worker_started":False,
            }
        except BaseException:
            db.execute("ROLLBACK")
            raise
    finally:
        db.close()


def release_index_supervisor(
    queue_path: Path,job_id: str,lease_token: str,generation: int,
    *,now_epoch: float | None=None,
) -> dict:
    return _change_lease(
        queue_path,job_id,lease_token,generation,release=True,now_epoch=now_epoch,
    )


def renew_index_supervisor(
    queue_path: Path,job_id: str,lease_token: str,generation: int,
    *,now_epoch: float | None=None,lease_seconds: float=120,
) -> dict:
    return _change_lease(
        queue_path,job_id,lease_token,generation,release=False,
        now_epoch=now_epoch,lease_seconds=lease_seconds,
    )


def inspect_index_supervisor(queue_path: Path) -> dict:
    """Read-only; never initializes an absent database or lease table."""
    path=_canonical_queue_path(queue_path)
    if not path.is_file():
        return {"state":"NOT_INITIALIZED","worker_started":False}
    with closing(_connect(path,create=False)) as cn:
        row=cn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='auto_worker_lease'"
        ).fetchone()
        if row is None:
            return {"state":"NOT_RESERVED","worker_started":False}
        owner=cn.execute(
            "SELECT job_id,lease_until_epoch,generation FROM "
            "auto_worker_lease WHERE singleton=1"
        ).fetchone()
    if owner is None or owner[0] is None:
        return {"state":"NOT_RESERVED","worker_started":False}
    return {
        "state":"LEASE_RECORDED","job_id":owner[0],
        "lease_until_epoch":owner[1],"generation":owner[2],
        "worker_started":False,
    }
