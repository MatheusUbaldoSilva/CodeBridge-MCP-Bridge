"""Protected generation reader (offline test-only).

Re-resolve pointer after acquiring generation lock to defeat pin/retire race.
"""
from contextlib import contextmanager
from pathlib import Path

from rag.runtime.generation_pointer import resolve_generation
from rag.runtime.generation_process_lock import generation_lock, GenerationBusy
from rag.runtime.generation_read_session import GenerationReadSession, GenerationReadError


@contextmanager
def protected_generation_read(test_root, *, retries=8):
    root = Path(test_root).resolve()
    if not isinstance(retries, int) or retries < 1:
        raise ValueError("retries must be >= 1")
    for _ in range(retries):
        chosen = resolve_generation(root)
        if chosen is None:
            raise GenerationReadError("no active generation")
        try:
            with generation_lock(root, chosen.generation):
                stable = resolve_generation(root)
                if stable is not None and stable.generation == chosen.generation:
                    yield GenerationReadSession(
                        name=chosen.generation, sqlite=chosen.sqlite,
                        qdrant=chosen.qdrant, manifest=chosen.manifest,
                    )
                    return
        except GenerationBusy:
            continue
    raise GenerationReadError("active generation changed or locked during acquisition")


@contextmanager
def protected_generation_retirement(test_root, name):
    """Acquire exclusivity only; caller must recheck active pointer under a wider publish lock."""
    root = Path(test_root).resolve()
    with generation_lock(root, name, exclusive=True):
        selected = resolve_generation(root)
        if selected is not None and selected.generation == name:
            raise GenerationReadError("cannot retire active generation")
        yield root / "generations" / name
