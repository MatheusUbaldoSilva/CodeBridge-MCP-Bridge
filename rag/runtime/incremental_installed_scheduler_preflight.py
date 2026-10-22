"""Read-only installed RAG scheduler preflight; never claims jobs."""
from __future__ import annotations

from pathlib import Path

from rag.runtime.incremental_scheduler_gate import assess_autonomous_worker_gate
from rag.runtime.status import resolve_rag_sqlite_path
from rag.runtime.incremental_scheduler_public_pointer import inspect_public_pointer_for_scheduler


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
    # A half-finished public generation transition forbids scheduling,
    # even when all feature switches were previously enabled.
    if (root / "production-generation-transition.json").exists():
        return {
            "state": "AUTONOMOUS_SCHEDULING_BLOCKED",
            "blockers": ["PUBLIC_GENERATION_TRANSITION_PENDING"],
            "worker_started": False, "scheduler_started": False,
            "active_index_updated": False, "safe_to_publish": False,
            "activation_authorized": False,
            "queue_db": str(path), "queue_present": path.is_file(),
            "installed_rag_root": str(root), "mode": "READ_ONLY_PREFLIGHT",
        }
    public_pointer = inspect_public_pointer_for_scheduler()
    if public_pointer["state"] not in ("PUBLIC_POINTER_OBSERVED", "PUBLIC_LEGACY_POINTER"):
        return {
            "state": "AUTONOMOUS_SCHEDULING_BLOCKED",
            "blockers": ["PUBLIC_POINTER_UNVERIFIED"],
            "public_pointer": public_pointer,
            "worker_started": False, "scheduler_started": False,
            "active_index_updated": False, "safe_to_publish": False,
            "activation_authorized": False,
            "queue_db": str(path), "queue_present": path.is_file(),
            "installed_rag_root": str(root), "mode": "READ_ONLY_PREFLIGHT",
        }
    # Installed operation must prove ownership of the exact durable supervisor
    # generation; the generic lab gate supports omissions, production cannot.
    expected_fence = root / "jobs" / "supervisor_fence.sqlite3"
    installed_fence_valid = (
        durable_store is not None
        and not Path(durable_store).is_symlink()
        and not Path(durable_store).parent.is_symlink()
        and Path(durable_store).resolve() == expected_fence.resolve()
        and type(expected_durable_generation) is int
        and expected_durable_generation >= 1
    )
    gate = assess_autonomous_worker_gate(
        path, queue_enabled=queue_enabled, worker_enabled=worker_enabled,
        scheduler_enabled=scheduler_enabled, approved_source_paths=approved_source_paths,
        installed_runtime_verified=installed_runtime_verified,
        recovery_verified=recovery_verified,
        public_integrity_verified=public_integrity_verified,
        durable_store=durable_store,
        expected_durable_generation=expected_durable_generation,
    )
    # A read-only snapshot is not an atomic release fence. Detect a changed
    # public pointer/journal and invalidate the apparent readiness.
    pointer_after = inspect_public_pointer_for_scheduler()
    blockers = list(gate["blockers"])
    if pointer_after != public_pointer or (root / "production-generation-transition.json").exists():
        blockers.append("PUBLIC_POINTER_CHANGED_DURING_PREFLIGHT")
    if not installed_fence_valid:
        blockers.append("INSTALLED_DURABLE_FENCE_REQUIRED")
    return {
        **gate,
        "state": "AUTONOMOUS_SCHEDULING_BLOCKED" if blockers else gate["state"],
        "blockers": blockers,
        "queue_db": str(path), "queue_present": path.is_file(),
        "installed_rag_root": str(root), "mode": "READ_ONLY_PREFLIGHT",
    }
