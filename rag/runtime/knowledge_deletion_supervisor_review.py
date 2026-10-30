"""RAG-DEL-01.04-T: strictly read-only observation of the AUTO supervisor.

A quiet observation is NOT a deletion authorization and is never a lock.
"""
from __future__ import annotations

from contextlib import closing
from hashlib import sha256
from pathlib import Path
import sqlite3

from rag.runtime.auto_index_queue import _canonical_queue_path


class DeletionSupervisorReviewError(RuntimeError):
    pass


_TERMINAL = frozenset(("CANCELLED", "FAILED"))


def inspect_deletion_supervisor_read_only(queue_path: Path) -> dict:
    """Inspect an existing queue without reservations, leases or status writes."""
    try:
        path = _canonical_queue_path(queue_path)
    except (ValueError, OSError) as exc:
        raise DeletionSupervisorReviewError("unsupported supervisor queue path") from exc
    for item in (path, path.parent, path.parent.parent):
        if item.exists() and (
            item.is_symlink() or (hasattr(item, "is_junction") and item.is_junction())
        ):
            raise DeletionSupervisorReviewError("redirected supervisor queue")
    result = {
        "state": "SUPERVISOR_REVIEW_BLOCKED_READ_ONLY",
        "queue_present": path.is_file(),
        "supervisor_observed_quiet": False,
        "queue_barrier_held": False,
        "operational_use_allowed": False,
        "activation_authorized": False,
        "read_only": True,
        "queue_identity_sha256": sha256(str(path.resolve()).encode("utf-8")).hexdigest(),
        "blockers": [],
    }
    if not path.is_file():
        result["blockers"].append("QUEUE_MISSING")
        return result
    try:
        with closing(sqlite3.connect(
            path.as_uri() + "?mode=ro", uri=True, timeout=0.5,
            isolation_level=None,
        )) as db:
            db.execute("PRAGMA query_only=ON")
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version != 1:
                result["blockers"].append("UNSUPPORTED_QUEUE_SCHEMA")
                return result
            tables = {
                row[0] for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name IN ('auto_worker_lease', 'auto_jobs')"
                )
            }
            if tables != {"auto_worker_lease", "auto_jobs"}:
                result["blockers"].append("SUPERVISOR_TABLES_MISSING")
                return result
            if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                result["blockers"].append("QUEUE_INTEGRITY_FAILED")
                return result
            rows = db.execute(
                "SELECT job_id,lease_token,lease_until_epoch,generation "
                "FROM auto_worker_lease WHERE singleton=1"
            ).fetchall()
            if len(rows) != 1 or type(rows[0][3]) is not int or rows[0][3] < 0:
                result["blockers"].append("LEASE_SINGLETON_INVALID")
                return result
            owner, token, until, gen = rows[0]
            result["supervisor_generation"] = gen
            result["lease_recorded"] = any(x is not None for x in (owner, token, until))
            if result["lease_recorded"]:
                result["blockers"].append("LEASE_RECONCILIATION_REQUIRED")
            states = dict(db.execute(
                "SELECT state,count(*) FROM auto_jobs GROUP BY state"
            ).fetchall())
            result["job_state_counts"] = states
            if any(state not in _TERMINAL for state in states):
                result["blockers"].append("UNRESOLVED_QUEUE_JOBS")
            if not result["blockers"]:
                result["state"] = "SUPERVISOR_OBSERVED_QUIET_READ_ONLY"
                result["supervisor_observed_quiet"] = True
    except sqlite3.Error as exc:
        raise DeletionSupervisorReviewError("supervisor review failed closed") from exc
    return result