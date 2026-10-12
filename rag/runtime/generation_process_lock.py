"""Windows test-only generation locks using native shared/exclusive byte locks.

A stable lock file is never deleted. Readers share byte zero; writers require
exclusive access. Never wired to production retirement or deletion.
"""
from __future__ import annotations
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import msvcrt
from pathlib import Path

class GenerationBusy(RuntimeError):
    pass

class _Overlapped(ctypes.Structure):
    _fields_ = [("Internal", ctypes.c_size_t),
                ("InternalHigh", ctypes.c_size_t),
                ("Offset", wintypes.DWORD),
                ("OffsetHigh", wintypes.DWORD),
                ("hEvent", wintypes.HANDLE)]

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_lock = _kernel32.LockFileEx
_lock.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
                  wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(_Overlapped)]
_lock.restype = wintypes.BOOL
_unlock = _kernel32.UnlockFileEx
_unlock.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
                    wintypes.DWORD, ctypes.POINTER(_Overlapped)]
_unlock.restype = wintypes.BOOL

@contextmanager
def generation_lock(test_root, generation, *, exclusive=False):
    root = Path(test_root).resolve()
    if root.name.casefold() != "codebridge-rag-generation-test":
        raise ValueError("locks restricted to test roots")
    if not isinstance(generation, str) or not generation.isidentifier() or len(generation) > 64:
        raise ValueError("invalid generation identifier")
    directory = root / "locks"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (generation + ".lock")
    # r+b on existing files; exclusive creation for new files. Do not use
    # append mode: it can request access that interferes with Windows locks.
    try:
        stream = open(path, "r+b", buffering=0)
    except FileNotFoundError:
        try:
            stream = open(path, "x+b", buffering=0)
        except FileExistsError:
            stream = open(path, "r+b", buffering=0)
    try:
        handle = wintypes.HANDLE(msvcrt.get_osfhandle(stream.fileno()))
        overlap = _Overlapped()
        flags = 1 | (2 if exclusive else 0)  # FAIL_IMMEDIATELY | EXCLUSIVE_LOCK
        if not _lock(handle, flags, 0, 1, 0, ctypes.byref(overlap)):
            code = ctypes.get_last_error()
            if code in (32, 33, 158):
                raise GenerationBusy("generation is busy")
            raise OSError(code, "LockFileEx failed")
        try:
            yield path
        finally:
            if not _unlock(handle, 0, 1, 0, ctypes.byref(overlap)):
                raise OSError(ctypes.get_last_error(), "UnlockFileEx failed")
    finally:
        stream.close()
