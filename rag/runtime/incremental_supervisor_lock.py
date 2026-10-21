"""Windows-only, nonblocking one-byte lock for isolated supervisor tests.

Does not start processes or permit RAG activation. On non-Windows, fails closed.
"""
from __future__ import annotations
from pathlib import Path
import os

try:
    import msvcrt
except ImportError:
    msvcrt = None


class SupervisorLock:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._handle = None

    def acquire(self) -> bool:
        if self._handle is not None:
            return False
        if msvcrt is None:
            return False
        # Caller supplies a preexisting isolated directory. Do not create
        # arbitrary paths, follow symlinks or touch active RAG data.
        if (self.path.is_symlink() or self.path.parent.is_symlink()
                or not self.path.parent.is_dir() or self.path.suffix != ".lock"):
            return False
        if self.path.exists() and not self.path.is_file():
            return False
        try:
            handle = open(self.path, "a+b", buffering=0)
            handle.seek(0)
            if not handle.read(1):
                handle.seek(0)
                handle.write(b"0")
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except (OSError, PermissionError):
            try:
                handle.close()
            except (NameError, OSError):
                pass
            return False
        self._handle = handle
        return True

    def release(self) -> bool:
        handle = self._handle
        if handle is None:
            return False
        self._handle = None
        try:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        finally:
            handle.close()
        return True

    def __enter__(self):
        if not self.acquire():
            raise RuntimeError("SUPERVISOR_LOCK_BUSY_OR_UNAVAILABLE")
        return self

    def __exit__(self, exc_type, exc, tb):
        self.release()
