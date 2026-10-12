"""Windows-only read-handle guard for closed synthetic snapshot sources."""
from __future__ import annotations

from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import os
from pathlib import Path


class FixtureFileBusy(RuntimeError):
    pass


@contextmanager
def hold_fixture_files_readonly(paths):
    """Hold all enumerated file handles with FILE_SHARE_READ only.

    This is not a global process-quiescence proof and is not for production.
    """
    if os.name != "nt":
        raise FixtureFileBusy("Windows lab handle probe required")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel32.CreateFileW
    create.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                       ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                       wintypes.HANDLE)
    create.restype = wintypes.HANDLE
    close = kernel32.CloseHandle
    close.argtypes = (wintypes.HANDLE,)
    close.restype = wintypes.BOOL
    handles = []
    invalid = ctypes.c_void_p(-1).value
    try:
        for raw_path in sorted(set(str(Path(p).absolute()) for p in paths)):
            handle = create(raw_path, 0x80000000, 0x1, None, 3, 0x80, None)
            if handle == invalid or handle is None:
                raise FixtureFileBusy("source file busy or inaccessible")
            handles.append(handle)
        yield
    finally:
        for handle in reversed(handles):
            close(handle)
