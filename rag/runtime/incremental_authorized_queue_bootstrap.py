"""Explicit, one-shot installed queue bootstrap contract for future MCP exposure.

No watcher, jobs, model process or index promotion. Default is read-only.
Production invocation is NOT performed by the tests or this module import.
"""
from __future__ import annotations

from contextlib import closing
import hashlib
import os
from pathlib import Path

from rag.runtime.incremental_installed_queue_bootstrap_preflight import (
    inspect_installed_queue_bootstrap,
)
from rag.runtime.incremental_job_queue import _connection, inspect_job_queue
from rag.runtime.incremental_scheduler_public_pointer import (
    inspect_public_pointer_for_scheduler,
)
from rag.runtime.incremental_supervisor_fence import issue_generation, observe_generation
from rag.runtime.incremental_supervisor_lock import SupervisorLock
from rag.runtime.status import resolve_rag_sqlite_path


def bootstrap_installed_queue(
    *, execute: bool = False, operator_approved: bool = False,
    confirmation: str | None = None, expected_generation: str | None = None,
) -> dict:
    def result(state: str, **details):
        return {
            "state": state, "executed": False,
            "scheduler_started": False, "worker_started": False,
            "job_enqueued": False, "active_index_updated": False,
            "safe_to_publish": False, **details,
        }

    # Evaluate the same pinned public source selected by MCP reader logic.
    selected_legacy = resolve_rag_sqlite_path()
    if selected_legacy.is_symlink() or selected_legacy.parent.is_symlink():
        return result("BOOTSTRAP_BLOCKED", reason="UNTRUSTED_LEGACY_REFERENCE")
    root = selected_legacy.resolve().parent
    localappdata = os.environ.get("LOCALAPPDATA")
    if (not localappdata
            or root != (Path(localappdata).resolve() / "CodeBridge" / "rag")
            or root.name != "rag" or root.parent.name != "CodeBridge"):
        return result("BOOTSTRAP_BLOCKED", reason="UNAPPROVED_INSTALLED_ROOT")
    jobs = root / "jobs"
    queue = jobs / "incremental_jobs.sqlite3"
    fence = jobs / "supervisor_fence.sqlite3"
    lock_path = jobs / "supervisor.lock"
    journal = root / "production-generation-transition.json"
    pointer_path = root / "active-generation.json"
    observed = inspect_installed_queue_bootstrap()
    pointer = inspect_public_pointer_for_scheduler()
    blockers = observed.get("blockers", [])
    allowed_pending = {"QUEUE_DIRECTORY_BOOTSTRAP_PENDING",
                       "QUEUE_SCHEMA_BOOTSTRAP_PENDING"}
    if (observed.get("state") != "BOOTSTRAP_BLOCKED"
            or len(blockers) != 1 or blockers[0] not in allowed_pending
            or pointer.get("state") != "PUBLIC_POINTER_OBSERVED"
            or observed.get("public_generation") != pointer.get("generation")):
        return result("BOOTSTRAP_BLOCKED",
                      reason="INSTALLED_PREFLIGHT_NOT_ELIGIBLE", blockers=blockers)
    if jobs.is_dir() and any(jobs.iterdir()):
        return result("BOOTSTRAP_BLOCKED", reason="UNRECOGNIZED_JOBS_CONTENT")
    if journal.exists() or journal.is_symlink() or pointer_path.is_symlink():
        return result("BOOTSTRAP_BLOCKED", reason="PUBLIC_TRANSITION_PENDING")
    pointer_before = pointer_path.read_bytes()
    generation = pointer["generation"]
    receipt = hashlib.sha256(pointer_before).hexdigest()[:16]
    required_confirmation = (
        f"CODEBRIDGE_RAG_QUEUE_BOOTSTRAP:{generation}:{receipt}"
    )
    if not execute:
        return result(
            "BOOTSTRAP_PLAN_ONLY", public_generation=generation,
            queue_path=str(queue), confirmation=required_confirmation,
            operator_approved=False, directory_created=False,
            preflight_blockers=blockers,
        )
    if (operator_approved is not True
            or confirmation != required_confirmation
            or expected_generation != generation):
        return result("BOOTSTRAP_AUTHORIZATION_MISMATCH",
                      reason="EXPLICIT_GENERATION_SCOPED_CONFIRMATION_REQUIRED")

    # A lock in the dedicated jobs directory serializes competing initializers.
    # No operations touch existing public index artifacts.
    created_directory = not jobs.is_dir()
    if created_directory:
        jobs.mkdir(exist_ok=False)
    if jobs.is_symlink() or queue.exists() or fence.exists():
        return result("BOOTSTRAP_BLOCKED", reason="QUEUE_ALREADY_CHANGED")
    with SupervisorLock(lock_path) as held:
        # Revalidate while holding exclusive process ownership.
        current = inspect_installed_queue_bootstrap()
        if (set(jobs.iterdir()) != {lock_path}
                or current.get("blockers") != ["QUEUE_SCHEMA_BOOTSTRAP_PENDING"]
                or pointer_path.read_bytes() != pointer_before
                or inspect_public_pointer_for_scheduler() != pointer
                or journal.exists() or journal.is_symlink()):
            return result("BOOTSTRAP_BLOCKED", reason="PREFLIGHT_CHANGED_AFTER_LOCK")
        try:
            with closing(_connection(queue, create=True)):
                pass
            issued = issue_generation(fence, lock=held)
            verified = inspect_job_queue(queue).get("state") == "QUEUE_INSPECTED"
            if verified:
                verified = observe_generation(fence, issued)
        except Exception as exc:
            # Never hide partially initialized storage behind executed=False.
            # Preserve artifacts for inspection; no automatic destructive reset.
            return result(
                "BOOTSTRAP_REVIEW_REQUIRED",
                executed=queue.is_file() or fence.is_file(),
                reason="INITIALIZATION_INTERRUPTED",
                error_type=type(exc).__name__,
                queue_present=queue.is_file(), fence_present=fence.is_file(),
            )
        if not verified:
            return result("BOOTSTRAP_REVIEW_REQUIRED", executed=True,
                          reason="POST_BOOTSTRAP_SCHEMA_OR_FENCE_UNVERIFIED")
        if (pointer_path.read_bytes() != pointer_before
                or inspect_public_pointer_for_scheduler() != pointer
                or journal.exists() or journal.is_symlink()):
            return result("BOOTSTRAP_REVIEW_REQUIRED", executed=True,
                          reason="PUBLIC_GENERATION_CHANGED_AFTER_BOOTSTRAP")
        return result(
            "QUEUE_BOOTSTRAPPED_NO_SCHEDULER", executed=True,
            queue_initialized=True, queue_path=str(queue),
            public_generation=generation,
            fence_generation=issued, operator_approved=True,
            directory_created=created_directory,
        )
