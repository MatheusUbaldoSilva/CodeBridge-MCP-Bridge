"""Shared/exclusive Windows lock for the real CodeBridge RAG generation cutover.

All production readers and writers must cooperate using this stable byte lock.
This primitive does NOT switch generation pointers or remove any files.
"""
from __future__ import annotations

from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import msvcrt
from pathlib import Path

from rag.runtime.status import resolve_rag_sqlite_path


class ProductionGenerationBusy(RuntimeError):
    pass


class _Overlapped(ctypes.Structure):
    _fields_ = [
        ("Internal", ctypes.c_size_t),
        ("InternalHigh", ctypes.c_size_t),
        ("Offset", wintypes.DWORD),
        ("OffsetHigh", wintypes.DWORD),
        ("hEvent", wintypes.HANDLE),
    ]


_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_lock = _kernel32.LockFileEx
_lock.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
    wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(_Overlapped),
]
_lock.restype = wintypes.BOOL
_unlock = _kernel32.UnlockFileEx
_unlock.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
    wintypes.DWORD, ctypes.POINTER(_Overlapped),
]
_unlock.restype = wintypes.BOOL


@contextmanager
def production_generation_lock(*, exclusive: bool = False, channel: str = "generation"):
    """Hold a cross-process shared/exclusive lock until context exit.

    LockFileEx uses byte zero, non-blocking acquisition, with Windows
    ERROR_LOCK_VIOLATION mapped to ProductionGenerationBusy. All callers
    must use this common lock; test-root generation locks are NOT compatible.
    """
    state = resolve_rag_sqlite_path().resolve().parent
    if state.name != "rag" or state.parent.name != "CodeBridge":
        raise ValueError("production generation lock requires CodeBridge RAG root")
    if not state.is_dir():
        raise ValueError("CodeBridge RAG root unavailable")
    # Semantic workers must serialize Qdrant Local/model startup without
    # blocking simultaneous protected lexical/status readers. Independent
    # channel names are a fixed allowlist, never caller-controlled filenames.
    names = {
        "generation": "production-generation.lock",
        "semantic": "production-semantic.lock",
    }
    if channel not in names:
        raise ValueError("unsupported CodeBridge lock channel")
    path = state / names[channel]
    try:
        stream = open(path, "r+b", buffering=0)
    except FileNotFoundError:
        try:
            stream = open(path, "x+b", buffering=0)
        except FileExistsError:
            stream = open(path, "r+b", buffering=0)
    try:
        handle = wintypes.HANDLE(msvcrt.get_osfhandle(stream.fileno()))
        over = _Overlapped()
        flags = 1 | (2 if exclusive else 0)
        if not _lock(handle, flags, 0, 1, 0, ctypes.byref(over)):
            code = ctypes.get_last_error()
            if code in (32, 33, 158):
                raise ProductionGenerationBusy("production generation is busy")
            raise OSError(code, "production LockFileEx failed")
        try:
            yield path
        finally:
            if not _unlock(handle, 0, 1, 0, ctypes.byref(over)):
                raise OSError(ctypes.get_last_error(), "production UnlockFileEx failed")
    finally:
        stream.close()
