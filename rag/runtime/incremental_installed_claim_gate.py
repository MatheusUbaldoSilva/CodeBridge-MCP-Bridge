"""Read-only ownership boundary before any future installed scheduler claim.

This check never acquires an OS lock, claims a queue row or starts a worker.
The caller must ALREADY hold the exact installed supervisor.lock.
"""
from __future__ import annotations

from pathlib import Path

from rag.runtime.incremental_installed_scheduler_preflight import inspect_installed_scheduler_preflight
from rag.runtime.incremental_supervisor_fence import observe_generation
from rag.runtime.incremental_supervisor_lock import SupervisorLock
from rag.runtime.status import resolve_rag_sqlite_path


def inspect_installed_claim_ownership(
    *, lock: SupervisorLock | None,
    expected_generation: int | None,
    approved_source_paths: tuple[str, ...] = (),
    queue_enabled: bool = False,
    worker_enabled: bool = False,
    scheduler_enabled: bool = False,
    recovery_verified: bool = False,
    installed_runtime_verified: bool = False,
    public_integrity_verified: bool = False,
) -> dict:
    root = resolve_rag_sqlite_path().resolve().parent
    jobs = root / "jobs"
    queue = jobs / "incremental_jobs.sqlite3"
    fence = jobs / "supervisor_fence.sqlite3"
    expected_lock = jobs / "supervisor.lock"

    def blocked(reason: str, **extra) -> dict:
        return {
            "state": "INSTALLED_CLAIM_BLOCKED", "blockers": [reason],
            "lock_owned": False, "queue_claimed": False,
            "worker_started": False, "active_index_updated": False,
            "activation_authorized": False, "safe_to_publish": False,
            **extra,
        }

    if (not isinstance(lock, SupervisorLock)
            or lock.path.is_symlink() or lock.path.parent.is_symlink()
            or lock.path.resolve() != expected_lock.resolve()
            or not lock.is_held()):
        return blocked("INSTALLED_SUPERVISOR_LOCK_NOT_OWNED")
    if (type(expected_generation) is not int or expected_generation < 1
            or not observe_generation(fence, expected_generation)):
        return blocked("INSTALLED_SUPERVISOR_GENERATION_STALE")
    report = inspect_installed_scheduler_preflight(
        queue_db=queue, durable_store=fence,
        expected_durable_generation=expected_generation,
        approved_source_paths=approved_source_paths,
        queue_enabled=queue_enabled, worker_enabled=worker_enabled,
        scheduler_enabled=scheduler_enabled,
        recovery_verified=recovery_verified,
        installed_runtime_verified=installed_runtime_verified,
        public_integrity_verified=public_integrity_verified,
    )
    if (not lock.is_held() or
            not observe_generation(fence, expected_generation)):
        return blocked("INSTALLED_SUPERVISOR_OWNERSHIP_CHANGED")
    if report["state"] != "PREREQUISITES_OBSERVED_ONLY":
        return blocked("INSTALLED_SCHEDULER_PREFLIGHT_BLOCKED",
                       preflight_blockers=report["blockers"])
    return {
        "state": "CLAIM_PREREQUISITES_OBSERVED_ONLY", "blockers": [],
        "lock_owned": True, "expected_generation": expected_generation,
        "queue_claimed": False, "worker_started": False,
        "active_index_updated": False, "activation_authorized": False,
        "safe_to_publish": False,
        "must_recheck_before_claim": True,
    }
