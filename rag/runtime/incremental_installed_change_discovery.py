"""Read-only discovery of stale sources in the installed public RAG generation.

This is an inventory, NOT an enqueue request or scheduler authorization.
"""
from __future__ import annotations

from pathlib import Path

from rag.runtime.production_source_freshness import assess_generation_source_freshness
from rag.runtime.incremental_scheduler_public_pointer import inspect_public_pointer_for_scheduler
from rag.runtime.status import resolve_rag_sqlite_path


def discover_installed_reindex_scope(project_root: str | Path) -> dict:
    pointer = inspect_public_pointer_for_scheduler()
    safe = {
        "read_only": True, "queue_updated": False, "worker_started": False,
        "active_index_updated": False, "safe_to_publish": False,
        "enqueue_authorized": False,
    }

    def blocked(reason: str) -> dict:
        return {**safe, "state": "DISCOVERY_BLOCKED", "blockers": [reason],
                "content_changed_paths": [], "missing_paths": []}

    if pointer["state"] not in ("PUBLIC_POINTER_OBSERVED", "PUBLIC_LEGACY_POINTER"):
        return blocked("PUBLIC_POINTER_UNVERIFIED")
    sqlite = resolve_rag_sqlite_path().resolve()
    # The status resolver intentionally locates the original legacy SQLite;
    # the live generation pointer is independent of that legacy path.
    installed_root = sqlite.parent
    if installed_root.name != "rag" or installed_root.parent.name != "CodeBridge":
        return blocked("UNAPPROVED_INSTALLED_RAG_ROOT")
    expected = (installed_root / "generations" / pointer["generation"]) if (
        pointer["generation"] != "legacy") else installed_root
    if sqlite.name != "rag_index.sqlite3" or not sqlite.is_file():
        return blocked("LEGACY_INDEX_REFERENCE_MISSING")
    if not (expected / "rag_index.sqlite3").is_file():
        return blocked("SELECTED_PUBLIC_INDEX_MISSING")
    if (installed_root / "production-generation-transition.json").exists():
        return blocked("PUBLIC_TRANSITION_PENDING")

    try:
        snapshot = assess_generation_source_freshness(expected, Path(project_root))
    except (OSError, ValueError, RuntimeError, TypeError, KeyError):
        return blocked("SOURCE_FRESHNESS_UNVERIFIED")

    if inspect_public_pointer_for_scheduler() != pointer or (
            installed_root / "production-generation-transition.json").exists():
        return blocked("PUBLIC_POINTER_CHANGED_DURING_DISCOVERY")

    return {
        **safe,
        "state": "INDEXED_SOURCES_DRIFT_FOUND" if snapshot["state"] == "SOURCE_SNAPSHOT_DRIFT"
                 else "INDEXED_SOURCES_CURRENT",
        "public_generation": pointer["generation"],
        "indexed_entries_checked": snapshot["indexed_entries_checked"],
        "content_changed_paths": snapshot["content_changed_paths"],
        "missing_paths": snapshot["missing_paths"],
        "new_unindexed_sources_assessed": False,
        "next_step": "INDIVIDUAL_GIT_APPROVAL_AND_PREQUEUE_REVIEW_REQUIRED",
    }
