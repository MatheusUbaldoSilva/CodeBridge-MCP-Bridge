"""RAG-DEL-01.04-P: strictly scratch-only writer fencing experiment.

This is not an activation API. It holds a SQLite BEGIN IMMEDIATE reservation
barrier while acquiring injected generation and semantic guards in that order.
Production callers are deliberately NOT supported.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sqlite3
import tempfile
from typing import Callable, ContextManager


class DeletionWriterFenceBlocked(RuntimeError):
    """Unsafe or unverified worker quiescence."""


def _scratch_queue_path(supplied: Path) -> Path:
    path = Path(supplied)
    if not path.is_absolute():
        raise DeletionWriterFenceBlocked("absolute scratch queue required")
    for item in (path, *path.parents):
        if item.exists() and (
            item.is_symlink() or (hasattr(item, "is_junction") and item.is_junction())
        ):
            raise DeletionWriterFenceBlocked("redirected scratch path")
    path = path.resolve()
    temp = Path(tempfile.gettempdir()).resolve()
    if (
        not path.is_relative_to(temp)
        or path.parents[2] == temp
        or not path.parents[2].name.startswith("tmp")
        or path.name != "auto_index_jobs.sqlite3"
        or path.parent.name != "jobs"
        or path.parent.parent.name != "auto"
        or not path.is_file()
    ):
        raise DeletionWriterFenceBlocked("existing temporary auto/jobs database required")
    return path


def _assert_no_live_or_runnable_workers(db: sqlite3.Connection) -> dict:
    version = db.execute("PRAGMA user_version").fetchone()[0]
    if version != 1:
        raise DeletionWriterFenceBlocked("unsupported supervisor queue version")
    tables = {
        row[0] for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name IN ('auto_worker_lease','auto_jobs')"
        )
    }
    if tables != {"auto_worker_lease", "auto_jobs"}:
        raise DeletionWriterFenceBlocked("supervisor tables missing")
    rows = db.execute(
        "SELECT job_id,lease_token,lease_until_epoch,generation "
        "FROM auto_worker_lease WHERE singleton=1"
    ).fetchall()
    if len(rows) != 1:
        raise DeletionWriterFenceBlocked("lease singleton missing or malformed")
    owner, token, until, generation = rows[0]
    # Expired leases are not considered clean: they need explicit recovery.
    if owner is not None or token is not None or until is not None:
        raise DeletionWriterFenceBlocked("worker lease requires separate reconciliation")
    if type(generation) is not int or generation < 0:
        raise DeletionWriterFenceBlocked("invalid lease generation")
    # Only terminal states qualify for a lab quiescence proof.
    # DRAFT and AWAITING_APPROVAL are refused too: they could become runnable
    # as soon as the reservation barrier is released.
    states = {row[0] for row in db.execute("SELECT DISTINCT state FROM auto_jobs")}
    if not states.issubset({"CANCELLED", "FAILED"}):
        raise DeletionWriterFenceBlocked("runnable or unresolved index jobs remain")
    return {"supervisor_generation": generation, "runnable_jobs": 0}


@contextmanager
def laboratory_writer_fence(
    queue_path: Path,
    generation_guard: Callable[[], ContextManager],
    semantic_guard: Callable[[], ContextManager],
    *,
    laboratory_mode: bool = False,
    operator_approved: bool = False,
    expected_freeze_generation: int | None = None,
):
    """Hold lab SQLite reservation barrier -> generation -> semantic locks.

    Does not mutate catalog, pointer, leases or indexes. Never use to activate.
    """
    if laboratory_mode is not True or operator_approved is not True:
        raise PermissionError("explicit scratch laboratory approval required")
    if not callable(generation_guard) or not callable(semantic_guard):
        raise DeletionWriterFenceBlocked("missing mandatory lock providers")
    queue = _scratch_queue_path(queue_path)
    try:
        db = sqlite3.connect(
            queue.as_uri() + "?mode=rw", uri=True,
            timeout=0.1, isolation_level=None,
        )
    except sqlite3.Error as exc:
        raise DeletionWriterFenceBlocked("queue connection unavailable") from exc
    try:
        try:
            db.execute("BEGIN IMMEDIATE")
        except sqlite3.Error as exc:
            raise DeletionWriterFenceBlocked("queue reservation barrier busy") from exc
        try:
            if expected_freeze_generation is not None:
                from rag.runtime.knowledge_deletion_reservation_freeze_lab import (
                    _read_marker_locked,
                )
                marker = _read_marker_locked(db)
                if (type(expected_freeze_generation) is not int
                        or expected_freeze_generation < 1
                        or marker is None or marker["state"] != "FROZEN"
                        or marker["generation"] != expected_freeze_generation):
                    raise DeletionWriterFenceBlocked(
                        "durable reservation freeze changed or absent")
            before = _assert_no_live_or_runnable_workers(db)
            with generation_guard():
                with semantic_guard():
                    after = _assert_no_live_or_runnable_workers(db)
                    if before != after:
                        raise DeletionWriterFenceBlocked("supervisor observation drift")
                    yield {
                        "state": "LAB_WRITER_FENCE_HELD",
                        **after,
                        "lock_order": ["queue", "generation", "semantic"],
                        "queue_barrier_held": True,
                        "operational_use_allowed": False,
                        "activation_authorized": False,
                    }
        finally:
            if db.in_transaction:
                db.execute("ROLLBACK")
    finally:
        db.close()