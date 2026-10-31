"""RAG-DEL-01.04-DQ-B: bounded cooperative catalog lock for scratch labs ONLY.

This lock is compatible with auto_index_canary._catalog_mutex on Windows,
but never accepts the installed catalog. Generation/semantic locks must be
acquired by the caller BEFORE this lock (DQ-C).
"""
from __future__ import annotations

from contextlib import contextmanager
import errno
import msvcrt
import os
from pathlib import Path
import tempfile
import time

from rag.runtime.knowledge_deletion_swap_lab import _lab_paths


class LaboratoryCatalogBusy(RuntimeError):
    """Catalog writer is busy; no lock was obtained before the deadline."""


class LaboratoryCatalogUnsafe(RuntimeError):
    """Untrusted or redirected scratch catalog/lock path."""


def _redirected(path: Path) -> bool:
    return path.is_symlink() or (
        hasattr(path, "is_junction") and path.is_junction()
    )


def _validated_scratch_catalog(catalog_file: Path) -> tuple[Path, Path]:
    path = Path(catalog_file).absolute()
    # The deletion lab's path guard also checks catalog name and temp ancestry.
    _lab_paths(path, path.parent / "active-generation.json")
    base = Path(tempfile.gettempdir()).resolve(strict=True)
    folder = path.parent
    if (_redirected(folder) or _redirected(path)
            or _redirected(folder / "auto-canary.lock")
            or folder.resolve(strict=True).parent != base
            or folder.name == "tmp"
            or not folder.name.startswith("tmp")
            or not path.is_file()):
        raise LaboratoryCatalogUnsafe("only existing, direct scratch catalog allowed")
    return path, folder


@contextmanager
def bounded_catalog_mutex_lab(
    catalog_file: Path, *, timeout_seconds: float = 0.4,
    laboratory_mode: bool = False, operator_approved: bool = False,
):
    """Take the real Win32 msvcrt byte-zero catalog lock with a bounded wait.

    No generated catalog data is modified. May create auto-canary.lock only
    in a verified direct TemporaryDirectory; a writer uses this SAME byte.
    """
    if laboratory_mode is not True or operator_approved is not True:
        raise PermissionError("scratch catalog lock requires explicit lab approval")
    if (type(timeout_seconds) not in (int, float)
            or timeout_seconds < 0 or timeout_seconds > 10
            or timeout_seconds != timeout_seconds
            or timeout_seconds == float("inf")):
        raise ValueError("timeout_seconds must be finite and within 0..10")
    catalog, folder = _validated_scratch_catalog(catalog_file)
    lock_path = folder / "auto-canary.lock"
    stream = None
    locked = False
    try:
        if _redirected(lock_path):
            raise LaboratoryCatalogUnsafe("redirected scratch catalog lock")
        # The existing writer opens a+b and locks byte 0. Match its semantics.
        stream = lock_path.open("a+b")
        if (_redirected(lock_path)
                or not os.path.samefile(lock_path, stream.name)):
            raise LaboratoryCatalogUnsafe("scratch lock path changed")
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        start = time.monotonic()
        while True:
            stream.seek(0)
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                locked = True
                break
            except OSError as exc:
                if exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                    raise
                remaining = timeout_seconds - (time.monotonic() - start)
                if remaining <= 0:
                    raise LaboratoryCatalogBusy("scratch catalog lock timed out") from exc
                time.sleep(min(0.015, remaining))
        # A path replacement while waiting could put a writer and reader on
        # different lock objects. Fail closed even if both names are files.
        active = os.fstat(stream.fileno())
        named = lock_path.stat(follow_symlinks=False)
        if ((active.st_dev, active.st_ino) != (named.st_dev, named.st_ino)
                or _redirected(lock_path) or _redirected(catalog)):
            raise LaboratoryCatalogUnsafe("catalog or lock redirected during wait")
        for journal in folder.glob("rag-del-*.journal.json"):
            if journal.exists() or _redirected(journal):
                raise LaboratoryCatalogUnsafe("unreconciled scratch deletion journal")
        yield catalog
    finally:
        if stream is not None:
            try:
                if locked:
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            finally:
                stream.close()