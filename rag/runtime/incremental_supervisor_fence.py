"""Isolated durable generation fence for future RAG supervisor experiments.

The caller MUST hold SupervisorLock for the entire duration of issuance.
This helper does not grant ownership, run jobs or publish an index.
"""
from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3

from rag.runtime.incremental_supervisor_lock import SupervisorLock


def issue_generation(store: Path, *, lock: SupervisorLock) -> int:
    if not isinstance(lock, SupervisorLock) or not lock.is_held():
        raise PermissionError("SUPERVISOR_LOCK_REQUIRED")
    path = Path(store)
    if lock.path.parent.resolve() != path.parent.resolve():
        raise PermissionError("SUPERVISOR_LOCK_SCOPE_MISMATCH")
    if path.is_symlink() or path.parent.is_symlink() or path.name != "supervisor_fence.sqlite3":
        raise ValueError("INVALID_FENCE_PATH")
    if not path.parent.is_dir():
        raise ValueError("FENCE_DIRECTORY_ABSENT")
    with closing(sqlite3.connect(path, timeout=5, isolation_level=None)) as db:
        db.execute("BEGIN IMMEDIATE")
        try:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            objects = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            if version == 0 and objects:
                raise ValueError("UNKNOWN_FENCE_DATABASE")
            if version not in (0, 1):
                raise ValueError("INVALID_FENCE_SCHEMA_VERSION")
            if version == 1:
                cols = {row[1] for row in db.execute("PRAGMA table_info(supervisor_fence)")}
                if cols != {"singleton", "generation"}:
                    raise ValueError("INVALID_FENCE_SCHEMA")
            else:
                db.execute("""CREATE TABLE supervisor_fence (
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    generation INTEGER NOT NULL CHECK(generation > 0))""")
                db.execute("PRAGMA user_version=1")
            db.execute("""INSERT INTO supervisor_fence(singleton,generation)
                VALUES(1,1) ON CONFLICT(singleton)
                DO UPDATE SET generation=generation+1""")
            generation = db.execute(
                "SELECT generation FROM supervisor_fence WHERE singleton=1").fetchone()[0]
            db.execute("COMMIT")
            return generation
        except BaseException:
            db.execute("ROLLBACK")
            raise


def observe_generation(store: Path, generation: int) -> bool:
    """No files are created; invalid or missing stores deny ownership."""
    path = Path(store)
    if type(generation) is not int or generation < 1:
        return False
    if (path.name != "supervisor_fence.sqlite3" or
            path.is_symlink() or path.parent.is_symlink() or not path.is_file()):
        return False
    try:
        with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
            db.execute("PRAGMA query_only=ON")
            if db.execute("PRAGMA user_version").fetchone()[0] != 1:
                return False
            row = db.execute(
                "SELECT generation FROM supervisor_fence WHERE singleton=1").fetchone()
            return row is not None and row[0] == generation
    except (OSError, sqlite3.Error):
        return False
