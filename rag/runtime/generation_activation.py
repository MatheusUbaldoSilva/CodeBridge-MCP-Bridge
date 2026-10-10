"""Atomic generation pointer switch for isolated tests; not wired to production."""
from __future__ import annotations
import json
import os
import re
from pathlib import Path
import tempfile

from rag.runtime.generation_pointer import resolve_generation, RagGenerationPointerError


class GenerationActivationError(RuntimeError):
    pass


def activate_test_generation(state_root, generation, *, fail_before_replace=False):
    root = Path(state_root).resolve()
    if "codebridge-rag-generation-test" not in {part.lower() for part in root.parts}:
        raise GenerationActivationError("activation is restricted to test roots")
    if not isinstance(generation, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}", generation):
        raise GenerationActivationError("invalid generation identifier")
    pointer = root / "active-generation.json"
    temp_pointer = None
    # Verify the prospective generation with the same resolver contract.
    try:
        candidate = root / "generations" / generation
        if candidate.name != generation or candidate.parent != root / "generations":
            raise GenerationActivationError("invalid generation name")
        if not candidate.is_dir():
            raise GenerationActivationError("generation missing")
        for part in ("rag_index.sqlite3", "rag-index-manifest.json", "qdrant"):
            if not (candidate / part).exists():
                raise GenerationActivationError("generation incomplete")
        payload = {"schema_version": 1, "generation": generation}
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=root, prefix=".active-generation.",
            suffix=".tmp", delete=False,
        ) as handle:
            temp_pointer = Path(handle.name)
            json.dump(payload, handle, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        if fail_before_replace:
            raise GenerationActivationError("injected interruption before pointer swap")
        os.replace(temp_pointer, pointer)
        temp_pointer = None
        selected = resolve_generation(root)
        if selected is None or selected.generation != generation:
            raise GenerationActivationError("activation verification failed")
        return selected
    finally:
        if temp_pointer is not None:
            temp_pointer.unlink(missing_ok=True)
