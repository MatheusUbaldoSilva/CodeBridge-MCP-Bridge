"""Read-only readiness probe for the future installed RAG jobs directory.

This deliberately never creates a folder, opens SQLite for writing or
grants permission to initialize a production queue.
"""
from __future__ import annotations

from pathlib import Path
from contextlib import closing
import sqlite3

from rag.runtime.incremental_job_queue import inspect_job_queue
from rag.runtime.incremental_scheduler_public_pointer import inspect_public_pointer_for_scheduler
from rag.runtime.status import resolve_rag_sqlite_path


def inspect_installed_queue_bootstrap() -> dict:
    def report(state: str, blockers: list[str], **details) -> dict:
        return {
            "state": state, "blockers": blockers,
            "read_only": True, "queue_initialized": False,
            "directory_created": False, "operator_authorized": False,
            "permission_to_bootstrap": False,
            "scheduler_started": False, "worker_started": False,
            "active_index_updated": False, "safe_to_publish": False,
            **details,
        }

    selected_legacy = resolve_rag_sqlite_path()
    if selected_legacy.parent.is_symlink() or selected_legacy.is_symlink():
        return report("BOOTSTRAP_BLOCKED", ["UNTRUSTED_LEGACY_REFERENCE"])
    legacy = selected_legacy.resolve()
    root = legacy.parent
    jobs = root / "jobs"
    queue = jobs / "incremental_jobs.sqlite3"
    pointer_before = inspect_public_pointer_for_scheduler()
    blockers: list[str] = []
    if (not root.is_dir() or root.is_symlink()
            or jobs.is_symlink() or queue.is_symlink()):
        return report("BOOTSTRAP_BLOCKED", ["UNTRUSTED_RAG_JOBS_DIRECTORY"])
    if pointer_before["state"] != "PUBLIC_POINTER_OBSERVED":
        blockers.append("PUBLIC_GENERATION_NOT_VERIFIED")
    else:
        selected = root / "generations" / pointer_before["generation"]
        if selected.is_symlink() or not (
            selected / "rag_index.sqlite3"
        ).is_file() or not (selected / "rag-index-manifest.json").is_file():
            blockers.append("SELECTED_PUBLIC_GENERATION_MISSING")
    journal = root / "production-generation-transition.json"
    if journal.exists() or journal.is_symlink():
        blockers.append("PUBLIC_TRANSITION_PENDING")
    if not legacy.is_file():
        blockers.append("LEGACY_SQLITE_REFERENCE_MISSING")
    if jobs.exists() and not jobs.is_dir():
        blockers.append("UNEXPECTED_JOBS_PATH_TYPE")
    if queue.exists():
        try:
            inspection = inspect_job_queue(queue)
            if inspection.get("state") != "QUEUE_INSPECTED":
                blockers.append("EXISTING_QUEUE_UNVERIFIED")
            else:
                with closing(sqlite3.connect(
                    queue.resolve().as_uri() + "?mode=ro", uri=True
                )) as cn:
                    cn.execute("PRAGMA query_only=ON")
                    if cn.execute("PRAGMA user_version").fetchone()[0] != 2:
                        blockers.append("QUEUE_SCHEMA_UPGRADE_REQUIRED")
        except (sqlite3.Error, OSError, ValueError):
            blockers.append("EXISTING_QUEUE_UNVERIFIED")
        queue_state = "EXISTING_QUEUE_NEEDS_SEPARATE_REVIEW"
    else:
        queue_state = "QUEUE_NOT_CREATED"
        blockers.append("QUEUE_DIRECTORY_BOOTSTRAP_PENDING" if not jobs.is_dir()
                        else "QUEUE_SCHEMA_BOOTSTRAP_PENDING")
    if pointer_before != inspect_public_pointer_for_scheduler() or journal.exists():
        blockers.append("PUBLIC_POINTER_CHANGED_DURING_INSPECTION")
    return report(
        "BOOTSTRAP_BLOCKED" if blockers else "EXISTING_QUEUE_OBSERVED_ONLY",
        blockers,
        public_generation=pointer_before.get("generation"),
        queue_path=str(queue),
        directory_present=jobs.is_dir(), queue_present=queue.is_file(),
        queue_state=queue_state,
        next_action="AUTHORIZED_SEPARATE_BOOTSTRAP_REQUIRED",
    )
