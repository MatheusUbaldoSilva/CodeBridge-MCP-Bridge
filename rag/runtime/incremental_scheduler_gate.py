"""Read-only eligibility gate for a future autonomous RAG worker scheduler.

This module never starts a worker, enables settings or mutates persistent state.
"""
from __future__ import annotations

from pathlib import Path
import sqlite3
from rag.runtime.incremental_job_queue import inspect_job_queue


def assess_autonomous_worker_gate(
    queue_db: Path, *, queue_enabled: bool = False,
    worker_enabled: bool = False, scheduler_enabled: bool = False,
    approved_source_paths: tuple[str, ...] = (),
    installed_runtime_verified: bool = False,
    recovery_verified: bool = False,
    public_integrity_verified: bool = False,
) -> dict:
    """Report blocking prerequisites; never grant publication authority."""
    blockers = []
    if queue_enabled is not True:
        blockers.append("QUEUE_DISABLED")
    if worker_enabled is not True:
        blockers.append("WORKER_DISABLED")
    if scheduler_enabled is not True:
        blockers.append("SCHEDULER_DISABLED")
    if not approved_source_paths or any(
        not isinstance(path, str) or not path.strip() or
        Path(path).is_absolute() or ".." in Path(path).parts
        for path in approved_source_paths
    ):
        blockers.append("SOURCE_APPROVAL_REQUIRED")
    if installed_runtime_verified is not True:
        blockers.append("INSTALLED_RUNTIME_UNVERIFIED")
    if recovery_verified is not True:
        blockers.append("RECOVERY_UNVERIFIED")
    if public_integrity_verified is not True:
        blockers.append("PUBLIC_INDEX_INTEGRITY_UNVERIFIED")
    if not Path(queue_db).is_file():
        blockers.append("QUEUE_STORE_ABSENT")
    else:
        try:
            inspection = inspect_job_queue(Path(queue_db))
            if inspection.get("state") != "QUEUE_INSPECTED":
                blockers.append("QUEUE_STORE_INVALID")
        except (sqlite3.Error, OSError, ValueError):
            blockers.append("QUEUE_STORE_INVALID")
    # This is only a diagnostic assessment, including when all prerequisites
    # appear present. No scheduler exists here and no activation is issued.
    return {
        "state": "AUTONOMOUS_SCHEDULING_BLOCKED" if blockers else "PREREQUISITES_OBSERVED_ONLY",
        "blockers": blockers,
        "scheduler_started": False,
        "worker_started": False,
        "active_index_updated": False,
        "safe_to_publish": False,
        "activation_authorized": False,
    }
