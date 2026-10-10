"""Pin all read paths to one immutable RAG generation per operation.

Offline/test opt-in only. Retention of generations while readers are active
must be handled before enabling production garbage collection.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import sqlite3

from rag.runtime.generation_pointer import resolve_generation, RagGenerationPointerError


class GenerationReadError(RuntimeError):
    pass


@dataclass(frozen=True)
class GenerationReadSession:
    name: str
    sqlite: Path
    qdrant: Path
    manifest: Path

    def open_sqlite(self):
        return sqlite3.connect(self.sqlite.resolve().as_uri() + "?mode=ro", uri=True)

    def open_qdrant(self):
        from rag.index.qdrant_local import open_qdrant_local
        return open_qdrant_local(self.qdrant)


def pin_generation_for_read(state_root):
    selected = resolve_generation(state_root)
    if selected is None:
        raise GenerationReadError("no active generation")
    return GenerationReadSession(
        name=selected.generation, sqlite=selected.sqlite,
        qdrant=selected.qdrant, manifest=selected.manifest,
    )
