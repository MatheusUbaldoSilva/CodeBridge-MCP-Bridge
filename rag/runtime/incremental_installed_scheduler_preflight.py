"""Read-only installed RAG scheduler preflight; never claims jobs."""
from __future__ import annotations

from pathlib import Path

from rag.runtime.incremental_scheduler_gate import assess_autonomous_worker_gate
from rag.runtime.status import resolve_rag_sqlite_path


def inspect_installed_scheduler_preflight(
    *, queue_db: Path | None = None,
    durable_store: Path | None = None,
    expected_durable_generation: int | None = None,
    approved_source_paths: tuple[str, ...] = (),
    queue_enabled: bool = False,
    worker_enabled: bool = False,
    scheduler_enabled: bool = False,
    recovery_verified: bool = False,
    installed_runtime_verified: bool = False,
    public_integrity_verified: bool = False,
) -> dict:
    root = resolve_rag_sqlite_path().resolve().parent
    # Never guess that the installed scheduler has been enabled.
    path = Path(queue_db) if queue_db is not None else root / "jobs" / "incremental_jobs.sqlite3"
    if (path.is_symlink() or path.parent.is_symlink() or
            path.name != "incremental_jobs.sqlite3" or path.parent.name != "jobs" or
            not path.resolve().is_relative_to(root)):
        return {
            "state": "AUTONOMOUS_SCHEDULING_BLOCKED",
            "blockers": ["QUEUE_PATH_OUTSIDE_INSTALLED_RAG"],
            "worker_started": False, "scheduler_started": False,
            "active_index_updated": False, "safe_to_publish": False,
            "activation_authorized": False,
        }
    gate = assess_autonomous_worker_gate(
        path, queue_enabled=queue_enabled, worker_enabled=worker_enabled,
        scheduler_enabled=scheduler_enabled, approved_source_paths=approved_source_paths,
        installed_runtime_verified=installed_runtime_verified,
        recovery_verified=recovery_verified,
        public_integrity_verified=public_integrity_verified,
        durable_store=durable_store,
        expected_durable_generation=expected_durable_generation,
    )
    return {
        **gate, "queue_db": str(path), "queue_present": path.is_file(),
        "installed_rag_root": str(root), "mode": "READ_ONLY_PREFLIGHT",
    }
