"""RAG-DEL-01.04-Y: durable reservation freeze in isolated scratch queue only.

The shared reservation gate may *read* this table on any queue, but this module
can only CREATE/MODIFY the table inside an existing OS temp lab queue.
No index deletion, worker launch, catalog or public-pointer mutation.
"""
from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3
import uuid

from rag.runtime.knowledge_deletion_writer_fence_lab import (
    _scratch_queue_path, DeletionWriterFenceBlocked,
)


class DeletionReservationFreezeError(RuntimeError):
    pass


_FREEZE_TABLE = "auto_deletion_reservation_freeze"
_SCHEMA = """CREATE TABLE IF NOT EXISTS auto_deletion_reservation_freeze (
    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
    schema_version INTEGER NOT NULL CHECK(schema_version=1),
    state TEXT NOT NULL CHECK(state IN ('OPEN','FROZEN')),
    token TEXT,
    generation INTEGER NOT NULL CHECK(generation>0),
    CHECK ((state='OPEN' AND token IS NULL)
        OR (state='FROZEN' AND token IS NOT NULL))
)"""
_EXPECTED_COLUMNS = (
    "singleton", "schema_version", "state", "token", "generation"
)


def _read_marker_locked(db: sqlite3.Connection) -> dict | None:
    """Read the existing marker under caller-owned SQLite transaction.

    Treat missing marker as feature absent; malformed marker is a hard block.
    This function never creates a table or writes a row.
    """
    exists = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (_FREEZE_TABLE,),
    ).fetchone()
    if exists is None:
        return None
    columns = tuple(
        row[1] for row in db.execute(f"PRAGMA table_info({_FREEZE_TABLE})")
    )
    if columns != _EXPECTED_COLUMNS:
        raise DeletionReservationFreezeError("freeze marker schema mismatch")
    rows = db.execute(
        f"SELECT singleton,schema_version,state,token,generation "
        f"FROM {_FREEZE_TABLE}"
    ).fetchall()
    if len(rows) != 1 or rows[0][0] != 1:
        raise DeletionReservationFreezeError("freeze singleton missing or ambiguous")
    _, version, state, token, generation = rows[0]
    if (type(version) is not int or version != 1
            or type(generation) is not int or generation < 1
            or state not in ("OPEN", "FROZEN")
            or (state == "OPEN" and token is not None)
            or (state == "FROZEN" and (
                not isinstance(token, str) or len(token) != 32
                or any(c not in "0123456789abcdef" for c in token)
            ))):
        raise DeletionReservationFreezeError("freeze marker invalid")
    return {"state": state, "token": token, "generation": generation}


def reject_if_deletion_reservations_frozen(db: sqlite3.Connection) -> None:
    """Fail closed in centralized supervisor reservation transaction."""
    row = _read_marker_locked(db)
    if row is not None and row["state"] == "FROZEN":
        raise DeletionReservationFreezeError("deletion reservation freeze is active")


def _lab_transaction(queue_path: Path):
    try:
        path = _scratch_queue_path(queue_path)
    except (ValueError, DeletionWriterFenceBlocked) as exc:
        raise DeletionReservationFreezeError("scratch queue only") from exc
    db = None
    try:
        db = sqlite3.connect(
            path.as_uri() + "?mode=rw", uri=True,
            timeout=0.2, isolation_level=None,
        )
        db.execute("PRAGMA busy_timeout=200")
        db.execute("BEGIN IMMEDIATE")
    except sqlite3.Error as exc:
        if db is not None:
            db.close()
        raise DeletionReservationFreezeError("scratch queue is busy") from exc
    return db


def freeze_deletion_reservations_lab(
    queue_path: Path, *,
    laboratory_mode: bool = False, operator_approved: bool = False,
) -> dict:
    if laboratory_mode is not True or operator_approved is not True:
        raise PermissionError("explicit scratch reservation-freeze approval required")
    db = _lab_transaction(queue_path)
    try:
        try:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            tables = {row[0] for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name IN ('auto_jobs','auto_worker_lease')"
            )}
            if version != 1 or tables != {"auto_jobs", "auto_worker_lease"}:
                raise DeletionReservationFreezeError("incomplete scratch supervisor")
            existing = _read_marker_locked(db)
            if existing is not None and existing["state"] == "FROZEN":
                raise DeletionReservationFreezeError("freeze already held")
            next_gen = 1 if existing is None else existing["generation"] + 1
            token = uuid.uuid4().hex
            db.execute(_SCHEMA)
            db.execute(
                f"INSERT INTO {_FREEZE_TABLE} "
                "(singleton,schema_version,state,token,generation) "
                "VALUES(1,1,'FROZEN',?,?) "
                "ON CONFLICT(singleton) DO UPDATE SET "
                "state=excluded.state, token=excluded.token, "
                "generation=excluded.generation",
                (token, next_gen),
            )
            db.execute("COMMIT")
            return {
                "state": "LAB_RESERVATIONS_FROZEN", "freeze_token": token,
                "freeze_generation": next_gen, "durable_marker": True,
                "workers_stopped": False, "activation_authorized": False,
                "operational_use_allowed": False,
            }
        except BaseException:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise
    finally:
        db.close()


def thaw_deletion_reservations_lab(
    queue_path: Path, freeze_token: str, freeze_generation: int, *,
    laboratory_mode: bool = False, operator_approved: bool = False,
) -> dict:
    if laboratory_mode is not True or operator_approved is not True:
        raise PermissionError("explicit scratch thaw approval required")
    if (not isinstance(freeze_token, str) or len(freeze_token) != 32
            or any(c not in "0123456789abcdef" for c in freeze_token)
            or type(freeze_generation) is not int or freeze_generation < 1):
        raise DeletionReservationFreezeError("invalid freeze ownership")
    db = _lab_transaction(queue_path)
    try:
        try:
            existing = _read_marker_locked(db)
            if (existing is None or existing["state"] != "FROZEN"
                    or existing["token"] != freeze_token
                    or existing["generation"] != freeze_generation):
                raise DeletionReservationFreezeError("stale or foreign freeze owner")
            db.execute(
                f"UPDATE {_FREEZE_TABLE} SET state='OPEN', token=NULL, "
                "generation=? WHERE singleton=1",
                (freeze_generation + 1,),
            )
            db.execute("COMMIT")
            return {
                "state": "LAB_RESERVATIONS_OPEN",
                "freeze_generation": freeze_generation + 1,
                "activation_authorized": False,
                "operational_use_allowed": False,
            }
        except BaseException:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise
    finally:
        db.close()