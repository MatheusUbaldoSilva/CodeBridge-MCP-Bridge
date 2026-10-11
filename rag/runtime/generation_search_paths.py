"""Opt-in paths adapter for isolated generation-backed searches.

Legacy production search is deliberately unchanged. Use the context manager
for the lifetime of all SQLite and Qdrant handles in a single operation.
"""
from __future__ import annotations
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from rag.runtime.generation_protected_session import protected_generation_read
from rag.runtime.generation_transition_journal import inspect_pending_transition


class GenerationSearchUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class SearchStoragePaths:
    generation: str
    sqlite: Path
    qdrant: Path
    manifest: Path


@contextmanager
def isolated_generation_search_paths(state_root):
    """Yield a consistent bundle while holding its cross-process reader lock."""
    root = Path(state_root).resolve()
    pending = inspect_pending_transition(root)
    if pending["state"] != "NO_PENDING_TRANSITION":
        raise GenerationSearchUnavailable("transition pending; recovery required")
    with protected_generation_read(root) as session:
        # Refuse to begin an operation while a transition is pending.
        # A normal activation without unfinished transitions is safe:
        # the session remains pinned and locked to the old generation.
        if inspect_pending_transition(root)["state"] != "NO_PENDING_TRANSITION":
            raise GenerationSearchUnavailable("transition pending; recovery required")
        yield SearchStoragePaths(
            generation=session.name,
            sqlite=session.sqlite,
            qdrant=session.qdrant,
            manifest=session.manifest,
        )
