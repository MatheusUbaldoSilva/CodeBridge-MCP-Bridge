"""Read-only eligibility gate for a future autonomous RAG worker scheduler.

This module never starts a worker, enables settings or mutates persistent state.
"""
from __future__ import annotations

from pathlib import Path
import sqlite3
from contextlib import closing
from rag.runtime.incremental_job_queue import inspect_job_queue
from rag.runtime.incremental_supervisor_fence import observe_generation


def assess_autonomous_worker_gate(
    queue_db: Path, *, queue_enabled: bool = False,
    worker_enabled: bool = False, scheduler_enabled: bool = False,
    approved_source_paths: tuple[str, ...] = (),
    installed_runtime_verified: bool = False,
    recovery_verified: bool = False,
    public_integrity_verified: bool = False,
    durable_store: Path | None = None,
    expected_durable_generation: int | None = None,
) -> dict:
    """Report blocking prerequisites; never grant publication authority."""
    blockers = []
    if durable_store is not None or expected_durable_generation is not None:
        if (durable_store is None or
                type(expected_durable_generation) is not int or
                not observe_generation(durable_store, expected_durable_generation)):
            blockers.append("DURABLE_FENCE_UNVERIFIED")
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
            else:
                uri = Path(queue_db).resolve().as_uri() + "?mode=ro"
                with closing(sqlite3.connect(uri, uri=True)) as connection:
                    connection.execute("PRAGMA query_only=ON")
                    version = connection.execute("PRAGMA user_version").fetchone()[0]
                    columns = {row[1] for row in connection.execute(
                        "PRAGMA table_info(jobs)")}
                    receipts = {row[1] for row in connection.execute(
                        "PRAGMA table_info(staging_receipts)")}
                    if (version != 2 or not {
                        "job_id", "state", "source_path", "observed_commit",
                        "observed_sha256", "attempts", "lease_token",
                        "lease_until_epoch", "due_at_epoch", "next_attempt_epoch",
                    }.issubset(columns) or not {
                        "job_id", "staging_path", "document_sha256",
                        "document_count", "chunk_count", "vector_count",
                        "validated_at_epoch",
                    }.issubset(receipts)):
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
