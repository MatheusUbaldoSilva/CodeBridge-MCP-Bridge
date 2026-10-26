"""RAG-AUTO-01.2: isolated durable draft queue for multi-project indexing.

The queue is NOT a worker, scheduler, approval system, or publisher. Drafts are
inert, and no import, read, or queue insertion launches indexing or model loads.
This storage is intentionally distinct from the installed incremental queue.
"""
from __future__ import annotations

from contextlib import closing
import json
import math
from pathlib import Path
import re
import sqlite3
import threading
import time
import uuid

_DB_NAME = "auto_index_jobs.sqlite3"
_PROJECT = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")
_REQUEST = re.compile(r"^[a-zA-Z0-9_-]{12,128}$")
_ALLOWED_SCOPES = frozenset(("BOTH", "CODE", "TEXT"))
_SCHEMA_VERSION = 1
_SCHEMA_INIT_LOCK = threading.RLock()
_STATES = (
    "DRAFT", "AWAITING_APPROVAL", "QUEUED", "RUNNING",
    "PAUSE_REQUESTED", "PAUSED", "CANCEL_REQUESTED", "CANCELLED",
    "VALIDATING", "READY_FOR_REVIEW", "FAILED",
)
_JOBS_SQL = """CREATE TABLE auto_jobs (
    job_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    source_root TEXT NOT NULL,
    requested_scope TEXT NOT NULL CHECK(requested_scope IN ('BOTH','CODE','TEXT')),
    idempotency_key TEXT NOT NULL UNIQUE,
    state TEXT NOT NULL CHECK(state IN (
      'DRAFT','AWAITING_APPROVAL','QUEUED','RUNNING','PAUSE_REQUESTED',
      'PAUSED','CANCEL_REQUESTED','CANCELLED','VALIDATING','READY_FOR_REVIEW','FAILED')),
    approved INTEGER NOT NULL DEFAULT 0 CHECK(approved IN (0,1)),
    file_count INTEGER NOT NULL DEFAULT 0 CHECK(file_count>=0),
    chunk_count INTEGER NOT NULL DEFAULT 0 CHECK(chunk_count>=0),
    text_vectors_done INTEGER NOT NULL DEFAULT 0 CHECK(text_vectors_done>=0),
    code_vectors_done INTEGER NOT NULL DEFAULT 0 CHECK(code_vectors_done>=0),
    candidate_generation TEXT,
    last_error TEXT,
    created_at_epoch REAL NOT NULL,
    updated_at_epoch REAL NOT NULL,
    CHECK(text_vectors_done+code_vectors_done<=chunk_count)
)"""
_EVENTS_SQL = """CREATE TABLE auto_job_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL REFERENCES auto_jobs(job_id),
    event_type TEXT NOT NULL,
    recorded_at_epoch REAL NOT NULL,
    details_json TEXT NOT NULL
)"""


class AutoIndexQueueError(RuntimeError):
    pass


def default_queue_path(home: Path | None = None) -> Path:
    """Storage is user-local and never under the production RAG database."""
    base = Path.home() if home is None else Path(home)
    return base / "CodeBridge-RAG-Workspace" / "auto" / "jobs" / _DB_NAME


def _canonical_queue_path(queue_path: Path) -> Path:
    path = Path(queue_path).absolute()
    if (path.name != _DB_NAME or path.parent.name != "jobs"
            or path.parent.parent.name != "auto"):
        raise ValueError("auto queue must be auto/jobs/auto_index_jobs.sqlite3")
    if any(parent.is_symlink() for parent in (
        path, path.parent, path.parent.parent,
    )):
        raise AutoIndexQueueError("symlink in auto queue path")
    return path


def _connect(path: Path, *, create: bool) -> sqlite3.Connection | None:
    path = _canonical_queue_path(path)
    if not create and not path.is_file():
        return None
    if create:
        path.parent.mkdir(parents=True, exist_ok=True)
    mode = "rwc" if create else "ro"
    connection = sqlite3.connect(
        path.as_uri() + f"?mode={mode}",
        uri=True, timeout=12, isolation_level=None,
    )
    try:
        connection.execute("PRAGMA busy_timeout=12000")
        connection.execute("PRAGMA foreign_keys=ON")
        if create:
            # Serialize concurrent first-use schema negotiation on the GUI.
            # BEGIN IMMEDIATE additionally serializes independent processes.
            with _SCHEMA_INIT_LOCK:
                if str(connection.execute(
                    "PRAGMA journal_mode"
                ).fetchone()[0]).lower() != "wal":
                    connection.execute("PRAGMA journal_mode=WAL")
                connection.execute("PRAGMA synchronous=FULL")
                connection.execute("BEGIN IMMEDIATE")
                try:
                    version = connection.execute("PRAGMA user_version").fetchone()[0]
                    if version == 0:
                        existing = connection.execute(
                            "SELECT count(*) FROM sqlite_master WHERE type IN ('table','view') "
                            "AND name NOT LIKE 'sqlite_%'"
                        ).fetchone()[0]
                        if existing:
                            raise AutoIndexQueueError("nonempty unversioned database")
                        connection.execute(_JOBS_SQL)
                        connection.execute(_EVENTS_SQL)
                        connection.execute(
                            "CREATE INDEX auto_jobs_created_idx ON "
                            "auto_jobs(created_at_epoch DESC, job_id)"
                        )
                        connection.execute(
                            "CREATE INDEX auto_events_job_idx ON "
                            "auto_job_events(job_id,event_id)"
                        )
                        connection.execute(f"PRAGMA user_version={_SCHEMA_VERSION}")
                    elif version != _SCHEMA_VERSION:
                        raise AutoIndexQueueError("unsupported auto queue schema version")
                    _check_schema(connection)
                    connection.execute("COMMIT")
                except BaseException:
                    if connection.in_transaction:
                        connection.execute("ROLLBACK")
                    raise
        else:
            connection.execute("PRAGMA query_only=ON")
            _check_schema(connection)
        return connection
    except BaseException:
        connection.close()
        raise


def _check_schema(connection: sqlite3.Connection) -> None:
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if version != _SCHEMA_VERSION:
        raise AutoIndexQueueError("auto queue version mismatch")
    required_jobs = {
        "job_id", "project_id", "source_root", "requested_scope", "state",
        "idempotency_key", "approved", "file_count", "chunk_count",
        "text_vectors_done", "code_vectors_done", "candidate_generation",
        "last_error", "created_at_epoch", "updated_at_epoch",
    }
    required_events = {
        "event_id","job_id","event_type","recorded_at_epoch","details_json"
    }
    columns = lambda table: {
        row[1] for row in connection.execute(f"PRAGMA table_info({table})")
    }
    if not required_jobs.issubset(columns("auto_jobs")) or not required_events.issubset(
        columns("auto_job_events")
    ):
        raise AutoIndexQueueError("auto queue schema incomplete")


def _validate_draft(project_id: str, source_root: str | Path,
                    idempotency_key: str, scope: str) -> Path:
    if not isinstance(project_id, str) or not _PROJECT.fullmatch(project_id):
        raise ValueError("invalid project namespace")
    if not isinstance(idempotency_key, str) or not _REQUEST.fullmatch(idempotency_key):
        raise ValueError("idempotency key must be 12-128 ASCII safe characters")
    if scope not in _ALLOWED_SCOPES:
        raise ValueError("scope must be BOTH, CODE or TEXT")
    requested = Path(source_root)
    if not requested.is_absolute() or requested.is_symlink():
        raise ValueError("source root must be a real absolute directory")
    root = requested.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("source root must be an existing directory")
    return root


def _to_job(row: tuple) -> dict:
    keys = (
        "job_id","project_id","source_root","requested_scope",
        "idempotency_key","state","approved","file_count","chunk_count",
        "text_vectors_done","code_vectors_done","candidate_generation",
        "last_error","created_at_epoch","updated_at_epoch",
    )
    return {k: (bool(v) if k == "approved" else v) for k, v in zip(keys, row)}


_COLUMNS = (
    "job_id,project_id,source_root,requested_scope,idempotency_key,state,"
    "approved,file_count,chunk_count,text_vectors_done,code_vectors_done,"
    "candidate_generation,last_error,created_at_epoch,updated_at_epoch"
)


def create_draft(
    queue_path: Path, *, project_id: str, source_root: str | Path,
    idempotency_key: str, scope: str = "BOTH", allow_write: bool = False,
    now_epoch: float | None = None,
) -> dict:
    """Explicitly create an inert draft; never approve, enqueue, or execute."""
    if allow_write is not True:
        raise PermissionError("explicit draft persistence authorization required")
    root = _validate_draft(project_id, source_root, idempotency_key, scope)
    now = time.time() if now_epoch is None else now_epoch
    if type(now) not in (int,float) or not math.isfinite(now) or now < 0:
        raise ValueError("invalid timestamp")
    path = _canonical_queue_path(queue_path)
    with closing(_connect(path, create=True)) as connection:
        connection.execute("BEGIN IMMEDIATE")
        try:
            existing = connection.execute(
                f"SELECT {_COLUMNS} FROM auto_jobs WHERE idempotency_key=?",
                (idempotency_key,),
            ).fetchone()
            if existing is not None:
                previous = _to_job(existing)
                if (previous["project_id"] != project_id
                        or previous["source_root"] != str(root)
                        or previous["requested_scope"] != scope):
                    raise AutoIndexQueueError("reused request key with different source")
                inserted = False
                job = previous
            else:
                job_id = uuid.uuid4().hex
                connection.execute(
                    "INSERT INTO auto_jobs(job_id,project_id,source_root,"
                    "requested_scope,idempotency_key,state,created_at_epoch,"
                    "updated_at_epoch) VALUES(?,?,?,?,?,'DRAFT',?,?)",
                    (job_id, project_id, str(root), scope, idempotency_key, now, now),
                )
                connection.execute(
                    "INSERT INTO auto_job_events(job_id,event_type,"
                    "recorded_at_epoch,details_json) VALUES(?,?,?,?)",
                    (job_id, "DRAFT_CREATED", now,
                     json.dumps({"requested_scope":scope},sort_keys=True)),
                )
                job = _to_job(connection.execute(
                    f"SELECT {_COLUMNS} FROM auto_jobs WHERE job_id=?",
                    (job_id,),
                ).fetchone())
                inserted = True
            connection.execute("COMMIT")
        except BaseException:
            connection.execute("ROLLBACK")
            raise
    return {
        **job, "inserted": inserted,
        "worker_started": False, "index_updated": False,
        "publication_authorized": False,
    }


def list_jobs(queue_path: Path, *, project_id: str | None = None,
              limit: int = 50) -> list[dict]:
    """Read only: does not create DB or start any indexing operation."""
    if project_id is not None and (
        not isinstance(project_id, str) or not _PROJECT.fullmatch(project_id)
    ):
        raise ValueError("invalid project namespace")
    if type(limit) is not int or not 1 <= limit <= 200:
        raise ValueError("limit must be between 1 and 200")
    connection = _connect(_canonical_queue_path(queue_path),create=False)
    if connection is None:
        return []
    with closing(connection):
        sql = f"SELECT {_COLUMNS} FROM auto_jobs"
        args = []
        if project_id is not None:
            sql += " WHERE project_id=?"
            args.append(project_id)
        sql += " ORDER BY created_at_epoch DESC,job_id DESC LIMIT ?"
        return [_to_job(row) for row in connection.execute(sql, (*args,limit))]


def get_job(queue_path: Path, job_id: str) -> dict | None:
    if not isinstance(job_id,str) or not re.fullmatch("[0-9a-f]{32}",job_id):
        raise ValueError("invalid job id")
    connection = _connect(_canonical_queue_path(queue_path),create=False)
    if connection is None:
        return None
    with closing(connection):
        row = connection.execute(
            f"SELECT {_COLUMNS} FROM auto_jobs WHERE job_id=?",(job_id,),
        ).fetchone()
        return _to_job(row) if row else None


def inspect_queue(queue_path: Path) -> dict:
    """Read-only health and counts; never initializes a missing database."""
    connection = _connect(_canonical_queue_path(queue_path),create=False)
    if connection is None:
        return {"state":"NOT_INITIALIZED","jobs":0,"worker_started":False}
    with closing(connection):
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise AutoIndexQueueError("auto queue failed integrity_check")
        count = connection.execute("SELECT count(*) FROM auto_jobs").fetchone()[0]
        states = dict(connection.execute(
            "SELECT state,count(*) FROM auto_jobs GROUP BY state"
        ).fetchall())
        return {
            "state":"READY","jobs":count,"by_state":states,
            "schema_version":_SCHEMA_VERSION,"integrity":integrity,
            "worker_started":False,"index_updated":False,
        }


def list_events(queue_path: Path, job_id: str) -> list[dict]:
    if get_job(queue_path,job_id) is None:
        return []
    with closing(_connect(_canonical_queue_path(queue_path),create=False)) as cn:
        return [
            {
                "event_id":event_id,"event_type":event_type,
                "recorded_at_epoch":stamp,
                "details":json.loads(details),
            }
            for event_id,event_type,stamp,details in cn.execute(
                "SELECT event_id,event_type,recorded_at_epoch,details_json "
                "FROM auto_job_events WHERE job_id=? ORDER BY event_id",(job_id,),
            )
        ]
