"""Initialize only the existing dedicated persistent RAG job queue schema.

No workers, events, index publication or scheduler services are started.
"""
from __future__ import annotations

from contextlib import closing
from pathlib import Path

from rag.runtime.incremental_job_queue import _connection, _database_path, inspect_job_queue
from rag.runtime.status import resolve_rag_sqlite_path


def initialize_installed_queue(*, operator_approved: bool = False) -> dict:
    if operator_approved is not True:
        return {"state": "OPERATOR_APPROVAL_REQUIRED", "initialized": False,
                "scheduler_started": False, "active_index_updated": False}
    root = resolve_rag_sqlite_path().resolve().parent
    path = root / "jobs" / "incremental_jobs.sqlite3"
    if root.is_symlink() or path.parent.is_symlink() or path.is_symlink():
        raise ValueError("untrusted installed queue path")
    if (root / "production-generation-transition.json").exists():
        raise RuntimeError("production transition is pending")
    with closing(_connection(_database_path(path), create=True)):
        pass
    result = inspect_job_queue(path)
    if result["state"] != "QUEUE_INSPECTED":
        raise RuntimeError("queue initialization did not pass inspection")
    return {
        "state": "QUEUE_INITIALIZED_NO_SCHEDULER",
        "initialized": True, "queue": str(path),
        "inspection": result, "scheduler_started": False,
        "worker_started": False, "active_index_updated": False,
    }
