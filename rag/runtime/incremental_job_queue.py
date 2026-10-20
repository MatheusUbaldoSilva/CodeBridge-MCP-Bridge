"""Durable V1.03-D-B job queue; no model worker, watcher, or publisher.

Persist only individually approved, committed CodeBridge sources. Every claim
revalidates Git HEAD, content SHA, source eligibility and debounce. SQLite
transactional claims are protected by BEGIN IMMEDIATE and expiring leases.
This module NEVER starts embeddings or changes live RAG generation files.
"""
from __future__ import annotations

from contextlib import closing
import hashlib
from pathlib import Path
import sqlite3
import time
from typing import Iterable
import uuid

from rag.runtime.incremental_job_prequeue import assess_commit_index_event

_DB_NAME = "incremental_jobs.sqlite3"
_SCHEMA = """CREATE TABLE IF NOT EXISTS jobs (
 job_id TEXT PRIMARY KEY,
 project_id TEXT NOT NULL CHECK(project_id='codebridge'),
 source_path TEXT NOT NULL,
 observed_commit TEXT NOT NULL,
 observed_sha256 TEXT NOT NULL,
 changed_at_epoch REAL NOT NULL,
 due_at_epoch REAL NOT NULL,
 debounce_seconds REAL NOT NULL,
 state TEXT NOT NULL CHECK(state IN
   ('PENDING','RETRY','CLAIMED','REJECTED','FAILED')),
 attempts INTEGER NOT NULL DEFAULT 0,
 lease_token TEXT,
 lease_until_epoch REAL,
 next_attempt_epoch REAL NOT NULL,
 last_error TEXT,
 created_at_epoch REAL NOT NULL,
 updated_at_epoch REAL NOT NULL,
 UNIQUE(project_id,source_path,observed_commit,observed_sha256)
)"""


def _database_path(db_path: Path) -> Path:
    specified = Path(db_path)
    if specified.is_symlink() or specified.parent.is_symlink():
        raise ValueError("symlinked job storage forbidden")
    db = specified.resolve()
    if db.name != _DB_NAME or db.parent.name != "jobs":
        raise ValueError("queue DB must live under its own jobs/incremental_jobs.sqlite3")
    return db


def _connection(db: Path, *, create: bool):
    if not create and not db.is_file():
        return None
    if create:
        db.parent.mkdir(parents=True, exist_ok=True)
    uri = db.as_uri() + ("?mode=rwc" if create else "?mode=rw")
    cn = sqlite3.connect(uri, uri=True, timeout=12, isolation_level=None)
    cn.execute("PRAGMA busy_timeout=12000")
    if create:
        # Refuse accidentally attaching or migrating an unrelated SQLite DB.
        version = cn.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, 1):
            cn.close()
            raise ValueError("unsupported queue schema version")
        if version == 0 and cn.execute(
            "SELECT count(*) FROM sqlite_master WHERE type='table'"
        ).fetchone()[0]:
            cn.close()
            raise ValueError("unversioned nonempty SQLite database")
        cn.execute("PRAGMA journal_mode=WAL")
        cn.execute("PRAGMA synchronous=FULL")
        cn.execute(_SCHEMA)
        cn.execute("PRAGMA user_version=1")
    elif cn.execute("PRAGMA user_version").fetchone()[0] != 1:
        cn.close()
        raise ValueError("unsupported queue schema")
    return cn


def _report(state: str, **fields) -> dict:
    return {
        "state": state, "project_id": "codebridge",
        "executed": False, "safe_to_publish": False,
        "active_index_updated": False, **fields,
    }


def enqueue_source_event(
    db_path: Path, project_root: Path, source_path: str, *,
    approved_paths: Iterable[str] = (),
    observed_commit: str, observed_sha256: str,
    changed_at_epoch: float, debounce_seconds: float = 30,
    now_epoch: float | None = None, queue_enabled: bool = False,
) -> dict:
    """Event must be explicitly enabled and individually allowlisted."""
    if queue_enabled is not True:
        return _report("AUTO_INDEX_DISABLED", queued=False)
    now = time.time() if now_epoch is None else float(now_epoch)
    eligible = assess_commit_index_event(
        project_root, source_path, approved_paths=approved_paths,
        observed_commit=observed_commit,
        observed_sha256=observed_sha256,
        changed_at_epoch=changed_at_epoch,
        debounce_seconds=debounce_seconds,
        now_epoch=now,
        indexing_enabled=True,
    )
    if eligible["state"] not in ("AWAITING_STABLE_COMMIT", "ELIGIBLE_FOR_DURABLE_QUEUE"):
        return _report(eligible["state"], queued=False)
    db = _database_path(db_path)
    job_id = hashlib.sha256(
        ("codebridge\0" + source_path + "\0" + observed_commit +
         "\0" + observed_sha256).encode("utf-8")
    ).hexdigest()
    due = changed_at_epoch + debounce_seconds
    with closing(_connection(db, create=True)) as cn:
        cn.execute("BEGIN IMMEDIATE")
        try:
            cn.execute(
                """INSERT OR IGNORE INTO jobs (
                job_id,project_id,source_path,observed_commit,observed_sha256,
                changed_at_epoch,due_at_epoch,debounce_seconds,state,
                next_attempt_epoch,created_at_epoch,updated_at_epoch)
                VALUES (?,'codebridge',?,?,?,?,?,?,'PENDING',?,?,?)""",
                (job_id, source_path, observed_commit, observed_sha256,
                 changed_at_epoch, due, debounce_seconds, due, now, now),
            )
            row = cn.execute(
                "SELECT state,attempts,due_at_epoch FROM jobs WHERE job_id=?",
                (job_id,),
            ).fetchone()
            cn.execute("COMMIT")
        except BaseException:
            cn.execute("ROLLBACK")
            raise
    queued = row[0] in ("PENDING", "RETRY", "CLAIMED")
    return _report(
        "QUEUED_DURABLY" if queued else "EXISTING_JOB_TERMINAL",
        queued=queued, job_id=job_id, job_state=row[0],
        attempts=row[1], ready_at_epoch=row[2],
        worker_started=False,
    )


def claim_approved_job(
    db_path: Path, project_root: Path, *,
    approved_paths: Iterable[str] = (), now_epoch: float | None = None,
    queue_enabled: bool = False, lease_seconds: float = 120,
    max_attempts: int = 3,
) -> dict:
    """Transactional reservation ONLY: never execute worker/indexer."""
    if queue_enabled is not True:
        return _report("AUTO_INDEX_DISABLED", claimed=False)
    if not (10 <= lease_seconds <= 3600 and 1 <= max_attempts <= 10):
        return _report("INVALID_CLAIM_POLICY", claimed=False)
    now = time.time() if now_epoch is None else float(now_epoch)
    db = _database_path(db_path)
    connection = _connection(db, create=False)
    if connection is None:
        return _report("QUEUE_EMPTY", claimed=False)
    with closing(connection) as cn:
        cn.execute("BEGIN IMMEDIATE")
        try:
            cn.execute(
                """UPDATE jobs SET state=CASE
                    WHEN attempts>=? THEN 'FAILED' ELSE 'RETRY' END,
                   lease_token=NULL,lease_until_epoch=NULL,
                   next_attempt_epoch=?, updated_at_epoch=?,
                   last_error='WORKER_LEASE_EXPIRED'
                   WHERE state='CLAIMED' AND lease_until_epoch<=?""",
                (max_attempts, now, now, now),
            )
            result = _report("QUEUE_EMPTY", claimed=False)
            # Scan bounded due events, cancelling stale ones and safely
            # allowing a newer approved event to be claimed in same transaction.
            for row in cn.execute(
                """SELECT job_id,source_path,observed_commit,observed_sha256,
                changed_at_epoch,debounce_seconds,attempts
                FROM jobs WHERE state IN ('PENDING','RETRY')
                AND next_attempt_epoch<=? AND due_at_epoch<=?
                ORDER BY due_at_epoch,created_at_epoch,job_id LIMIT 5""",
                (now, now),
            ).fetchall():
                job, path, commit, sha, changed, debounce, attempts = row
                check = assess_commit_index_event(
                    project_root, path, approved_paths=approved_paths,
                    observed_commit=commit, observed_sha256=sha,
                    changed_at_epoch=changed, debounce_seconds=debounce,
                    now_epoch=now, indexing_enabled=True,
                )
                if check["state"] != "ELIGIBLE_FOR_DURABLE_QUEUE":
                    cn.execute(
                        """UPDATE jobs SET state='REJECTED',last_error=?,
                        updated_at_epoch=? WHERE job_id=?""",
                        (check["state"], now, job),
                    )
                    continue
                token = uuid.uuid4().hex
                cn.execute(
                    """UPDATE jobs SET state='CLAIMED', attempts=?,
                    lease_token=?,lease_until_epoch=?,updated_at_epoch=?,
                    last_error=NULL WHERE job_id=?""",
                    (attempts + 1, token, now + lease_seconds, now, job),
                )
                result = _report("CLAIMED_FOR_OFFLINE_STAGING", claimed=True,
                                 job_id=job, lease_token=token,
                                 lease_until_epoch=now + lease_seconds,
                                 source_path=path, observed_sha256=sha,
                                 observed_commit=commit, attempts=attempts + 1,
                                 worker_started=False)
                break
            cn.execute("COMMIT")
        except BaseException:
            cn.execute("ROLLBACK")
            raise
    return result


def report_staging_failure(
    db_path: Path, job_id: str, lease_token: str, *,
    reason: str, now_epoch: float | None = None,
    queue_enabled: bool = False, max_attempts: int = 3,
    retry_delay_seconds: float = 30,
) -> dict:
    """Bounded retry; only the current unexpired lease owner can act."""
    if queue_enabled is not True:
        return _report("AUTO_INDEX_DISABLED")
    if not (1 <= max_attempts <= 10 and 0 <= retry_delay_seconds <= 3600
            and isinstance(reason, str) and 0 < len(reason) <= 200):
        return _report("INVALID_FAILURE_POLICY")
    now = time.time() if now_epoch is None else float(now_epoch)
    db = _database_path(db_path)
    connection = _connection(db, create=False)
    if connection is None:
        return _report("QUEUE_EMPTY")
    with closing(connection) as cn:
        cn.execute("BEGIN IMMEDIATE")
        try:
            row = cn.execute(
                """SELECT attempts,lease_until_epoch FROM jobs
                WHERE job_id=? AND lease_token=? AND state='CLAIMED'""",
                (job_id, lease_token),
            ).fetchone()
            if row is None or row[1] <= now:
                result = _report("STALE_OR_EXPIRED_LEASE")
            else:
                retry = row[0] < max_attempts
                state = "RETRY" if retry else "FAILED"
                cn.execute(
                    """UPDATE jobs SET state=?,lease_token=NULL,
                    lease_until_epoch=NULL,next_attempt_epoch=?,
                    last_error=?,updated_at_epoch=? WHERE job_id=?""",
                    (state, now + retry_delay_seconds if retry else now,
                     reason, now, job_id),
                )
                result = _report("SCHEDULED_RETRY" if retry else "FAILED_MAX_ATTEMPTS",
                                 job_id=job_id, attempts=row[0])
            cn.execute("COMMIT")
        except BaseException:
            cn.execute("ROLLBACK")
            raise
    return result


def inspect_job_queue(db_path: Path) -> dict:
    """Read-only job counts; never create the queue DB."""
    db = _database_path(db_path)
    if not db.is_file():
        return _report("QUEUE_NOT_INITIALIZED", total=0, by_state={})
    with closing(sqlite3.connect(db.as_uri() + "?mode=ro", uri=True)) as cn:
        cn.execute("PRAGMA query_only=ON")
        if cn.execute("PRAGMA user_version").fetchone()[0] != 1:
            raise ValueError("unexpected job queue schema")
        items = cn.execute(
            "SELECT state,count(*) FROM jobs GROUP BY state"
        ).fetchall()
    return _report("QUEUE_INSPECTED", total=sum(x[1] for x in items),
                   by_state=dict(items))
