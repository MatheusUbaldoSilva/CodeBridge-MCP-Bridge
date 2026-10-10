"""Windows cross-process generation lifetime lock, test-only.

Readers hold a shared byte-range lock; retirement requires exclusive lock.
No deletion or production wiring is provided.
"""
from __future__ import annotations
from contextlib import contextmanager
from pathlib import Path
import msvcrt
import os

class GenerationBusy(RuntimeError):
    pass

@contextmanager
def generation_lock(test_root, generation, *, exclusive=False):
    root = Path(test_root).resolve()
    if "codebridge-rag-generation-test" not in {p.lower() for p in root.parts}:
        raise ValueError("locks restricted to test roots")
    if not generation.isidentifier() or len(generation) > 64:
        raise ValueError("invalid generation identifier")
    directory = root / "locks"
    directory.mkdir(exist_ok=True, parents=True)
    path = directory / (generation + ".lock")
    # Keep lock file persistent so its identity cannot change between contenders.
    handle = open(path, "a+b", buffering=0)
    try:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.seek(0)
            handle.write(b"0")
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK if exclusive else msvcrt.LK_NBRLCK, 1)
        except OSError as exc:
            raise GenerationBusy("generation has another reader or writer") from exc
        try:
            yield path
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    finally:
        handle.close()
