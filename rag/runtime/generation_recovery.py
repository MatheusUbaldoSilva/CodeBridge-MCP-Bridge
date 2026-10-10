"""Conservative startup inspection for isolated RAG generation tests.

Never guesses a replacement active generation. Never deletes files.
"""
from __future__ import annotations
from pathlib import Path
from rag.runtime.generation_pointer import resolve_generation, RagGenerationPointerError


def inspect_test_generation_recovery(state_root):
    root = Path(state_root).resolve()
    if "codebridge-rag-generation-test" not in {p.lower() for p in root.parts}:
        raise ValueError("recovery inspection restricted to test roots")
    pointer = root / "active-generation.json"
    stale = sorted(path.name for path in root.glob(".active-generation.*.tmp") if path.is_file())
    try:
        selected = resolve_generation(root)
    except RagGenerationPointerError as exc:
        return {"state": "BLOCKED_MANUAL_RECOVERY", "active": None,
                "reason": str(exc), "temporary_pointer_files": stale}
    if selected is None:
        return {"state": "LEGACY_OR_NOT_ACTIVATED", "active": None,
                "temporary_pointer_files": stale}
    return {"state": "ACTIVE_GENERATION_AVAILABLE", "active": selected.generation,
            "temporary_pointer_files": stale, "paths": {
                "sqlite": str(selected.sqlite), "qdrant": str(selected.qdrant),
                "manifest": str(selected.manifest)}}
