"""Production RAG reader pin held through the complete SQLite/vector operation.

This primitive does not itself migrate legacy MCP handlers. Activation must
remain prohibited until all search and get-context handlers use it.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from dataclasses import dataclass
import json
import re

from rag.runtime.status import resolve_rag_sqlite_path, resolve_rag_manifest_path
from rag.index.qdrant_local import resolve_qdrant_local_path
_GEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


@dataclass(frozen=True)
class SearchStoragePaths:
    generation: str
    sqlite: Path
    qdrant: Path
    manifest: Path


def _read_pointer(state: Path):
    pointer = state / "active-generation.json"
    if not pointer.is_file():
        return None
    data = json.loads(pointer.read_text(encoding="utf-8"))
    name = data.get("generation")
    if data.get("schema_version") != 1 or not isinstance(name, str) or not _GEN.fullmatch(name):
        raise RuntimeError("invalid production generation pointer")
    root = (state / "generations").resolve()
    folder = (root / name).resolve(strict=True)
    if not folder.is_relative_to(root) or not folder.is_dir():
        raise RuntimeError("generation outside versioned storage")
    return SearchStoragePaths(
        generation=name, sqlite=folder / "rag_index.sqlite3",
        qdrant=folder / "qdrant", manifest=folder / "rag-index-manifest.json",
    )

from rag.runtime.production_generation_lock import production_generation_lock


@contextmanager
def production_generation_read():
    with production_generation_lock(exclusive=False):
        state = resolve_rag_sqlite_path().resolve().parent
        pointer = _read_pointer(state)
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
        # The legacy lexical-only API historically accepts a SQLite index
        # without Qdrant or manifest (e.g. tiny source fixture indices).
        # A versioned generation, in contrast, must contain all 3 stores.
        if not paths.sqlite.is_file() or (
            pointer is not None and (
                not paths.qdrant.is_dir() or not paths.manifest.is_file()
            )
        ):
            raise RuntimeError("production generation incomplete")
        yield paths
