"""Test-only atomic generation activation serialized with retirement.

No production reader or publication entry point calls this module.
"""
from __future__ import annotations
import json
import os
import re
import tempfile
from pathlib import Path
from rag.runtime.generation_pointer import resolve_generation
from rag.runtime.generation_process_lock import generation_lock

PUBLICATION_LOCK_NAME = "__publication__"


class GenerationActivationError(RuntimeError):
    pass


def activate_test_generation(state_root, generation, *, fail_before_replace=False):
    root = Path(state_root).resolve()
    if "codebridge-rag-generation-test" not in {part.lower() for part in root.parts}:
        raise GenerationActivationError("activation restricted to test roots")
    if not isinstance(generation, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}", generation):
        raise GenerationActivationError("invalid generation identifier")
    with generation_lock(root, PUBLICATION_LOCK_NAME, exclusive=True):
        candidate = root / "generations" / generation
        if not candidate.is_dir():
            raise GenerationActivationError("generation missing")
        if not (candidate / "rag_index.sqlite3").is_file() or not (candidate / "rag-index-manifest.json").is_file() or not (candidate / "qdrant").is_dir():
            raise GenerationActivationError("generation incomplete")
        # The publication lock serializes activation with retirement.
        if candidate.is_dir():
            pointer = root / "active-generation.json"
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8", dir=root,
                    prefix=".active-generation.", suffix=".tmp", delete=False,
                ) as handle:
                    temporary = Path(handle.name)
                    json.dump({"schema_version": 1, "generation": generation}, handle, sort_keys=True)
                    handle.flush()
                    os.fsync(handle.fileno())
                if fail_before_replace:
                    raise GenerationActivationError("injected interruption before pointer swap")
                os.replace(temporary, pointer)
                temporary = None
                selected = resolve_generation(root)
                if selected is None or selected.generation != generation:
                    raise GenerationActivationError("activation verification failed")
                return selected
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
