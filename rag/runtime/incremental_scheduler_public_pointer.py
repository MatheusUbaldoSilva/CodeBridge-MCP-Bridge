"""Read-only inspection of the active RAG pointer and transition journal."""
from __future__ import annotations

import json
from pathlib import Path

from rag.runtime.status import resolve_rag_sqlite_path


def inspect_public_pointer_for_scheduler() -> dict:
    root = resolve_rag_sqlite_path().resolve().parent
    pointer = root / "active-generation.json"
    journal = root / "production-generation-transition.json"
    if journal.exists() or journal.is_symlink():
        return {
            "state": "PUBLIC_TRANSITION_PENDING",
            "generation": None, "safe_to_schedule": False, "read_only": True,
        }
    if not pointer.exists():
        return {
            "state": "PUBLIC_LEGACY_POINTER",
            "generation": "legacy", "safe_to_schedule": False, "read_only": True,
        }
    if pointer.is_symlink() or not pointer.is_file():
        return {
            "state": "PUBLIC_POINTER_INVALID",
            "generation": None, "safe_to_schedule": False, "read_only": True,
        }
    try:
        value = json.loads(pointer.read_text(encoding="utf-8"))
        generation = value.get("generation")
        if (value.get("schema_version") != 1 or not isinstance(generation, str)
                or not generation.startswith("v1_delta_") or
                len(generation) != 23):
            raise ValueError("invalid public pointer")
    except (OSError, ValueError, TypeError, AttributeError):
        return {
            "state": "PUBLIC_POINTER_INVALID",
            "generation": None, "safe_to_schedule": False, "read_only": True,
        }
    return {
        "state": "PUBLIC_POINTER_OBSERVED",
        "generation": generation, "safe_to_schedule": False, "read_only": True,
    }
