"""Production RAG reader pin held through the complete SQLite/vector operation.

This primitive does not itself migrate legacy MCP handlers. Activation must
remain prohibited until all search and get-context handlers use it.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from rag.runtime.status import resolve_rag_sqlite_path, resolve_rag_manifest_path
from rag.index.qdrant_local import resolve_qdrant_local_path
from rag.runtime.generation_pointer import resolve_generation
from rag.runtime.generation_search_paths import SearchStoragePaths
from rag.runtime.production_generation_lock import production_generation_lock


@contextmanager
def production_generation_read():
    with production_generation_lock(exclusive=False):
        state = resolve_rag_sqlite_path().resolve().parent
        pointer = resolve_generation(state)
        if pointer is None:
            paths = SearchStoragePaths(
                generation="legacy",
                sqlite=resolve_rag_sqlite_path().resolve(),
                qdrant=resolve_qdrant_local_path().resolve(),
                manifest=resolve_rag_manifest_path().resolve(),
            )
        else:
            paths = SearchStoragePaths(
                generation=pointer.generation,
                sqlite=pointer.sqlite,
                qdrant=pointer.qdrant,
                manifest=pointer.manifest,
            )
        if not paths.sqlite.is_file() or not paths.qdrant.is_dir() or not paths.manifest.is_file():
            raise RuntimeError("production generation incomplete")
        yield paths
