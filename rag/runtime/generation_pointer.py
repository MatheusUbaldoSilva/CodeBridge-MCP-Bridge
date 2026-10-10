"""Resolve an immutable RAG generation from one pointer snapshot.

Opt-in only; existing production readers retain their legacy paths.
"""
from __future__ import annotations
from dataclasses import dataclass
import json
from pathlib import Path
import re


class RagGenerationPointerError(RuntimeError):
    pass


_GENERATION = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")


@dataclass(frozen=True)
class RagGenerationPaths:
    generation: str
    sqlite: Path
    qdrant: Path
    manifest: Path


def resolve_generation(state_root, *, pointer_name="active-generation.json"):
    root = Path(state_root).resolve()
    pointer = root / pointer_name
    if not pointer.is_file():
        return None
    try:
        payload = json.loads(pointer.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RagGenerationPointerError("invalid generation pointer") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise RagGenerationPointerError("unsupported generation pointer")
    name = payload.get("generation")
    if not isinstance(name, str) or not _GENERATION.fullmatch(name):
        raise RagGenerationPointerError("unsafe generation identifier")
    directory = (root / "generations" / name).resolve()
    if not directory.is_relative_to(root / "generations") or not directory.is_dir():
        raise RagGenerationPointerError("generation unavailable")
    sqlite = directory / "rag_index.sqlite3"
    manifest = directory / "rag-index-manifest.json"
    vectors = directory / "qdrant"
    if not sqlite.is_file() or not manifest.is_file() or not vectors.is_dir():
        raise RagGenerationPointerError("generation incomplete")
    return RagGenerationPaths(name, sqlite, vectors, manifest)
