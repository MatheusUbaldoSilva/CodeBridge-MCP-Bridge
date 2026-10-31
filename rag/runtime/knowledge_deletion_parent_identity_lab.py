"""DQ-E-D-3C-G-2: Windows process-object identity checks for TEMP IPC.

Not an authentication token or a substitute for trusted inherited IPC handles.
This lab-only module verifies a pinned process PID + creation FILETIME and
holds a Win32 process object handle so PID reuse cannot redirect liveness.

Windows venv redirectors can create the final Python interpreter as an
intermediate child; os.getppid() is NOT a sound direct-parent authorization
test for our CodeBridge environment.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
from typing import NamedTuple


_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_STILL_ACTIVE = 259
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_open_process = _kernel32.OpenProcess
_open_process.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
_open_process.restype = wintypes.HANDLE
_get_exit_code = _kernel32.GetExitCodeProcess
_get_exit_code.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
_get_exit_code.restype = wintypes.BOOL
_close_handle = _kernel32.CloseHandle
_close_handle.argtypes = [wintypes.HANDLE]
_close_handle.restype = wintypes.BOOL
_get_process_times = _kernel32.GetProcessTimes
_get_process_times.argtypes = [
    wintypes.HANDLE, ctypes.POINTER(wintypes.FILETIME),
    ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME),
    ctypes.POINTER(wintypes.FILETIME),
]
_get_process_times.restype = wintypes.BOOL


class ProcessIdentityLabError(PermissionError):
    pass


def _parse_pid(value: str) -> int:
    if (type(value) is not str or not value.isascii() or not value.isdecimal()
            or not 1 <= len(value) <= 10):
        raise ProcessIdentityLabError("invalid parent PID")
    pid = int(value)
    if not 1 <= pid < 0xFFFFFFFF:
        raise ProcessIdentityLabError("invalid parent PID range")
    return pid


def _parse_creation(value: str) -> int:
    if (type(value) is not str or not value.isascii() or not value.isdecimal()
            or not 1 <= len(value) <= 20):
        raise ProcessIdentityLabError("invalid parent birth FILETIME")
    birth = int(value)
    if not 1 <= birth <= 0xFFFFFFFFFFFFFFFF:
        raise ProcessIdentityLabError("invalid parent birth FILETIME range")
    return birth


def _creation_filetime(handle) -> int:
    created = wintypes.FILETIME()
    exited = wintypes.FILETIME()
    kernel = wintypes.FILETIME()
    user = wintypes.FILETIME()
    if not _get_process_times(
        handle, ctypes.byref(created), ctypes.byref(exited),
        ctypes.byref(kernel), ctypes.byref(user),
    ):
        raise ProcessIdentityLabError("cannot attest scratch process birth")
    return (created.dwHighDateTime << 32) | created.dwLowDateTime


def _process_alive(handle) -> bool:
    code = wintypes.DWORD(0)
    return bool(_get_exit_code(handle, ctypes.byref(code))) and code.value == _STILL_ACTIVE


def _open_identity_handle(pid: int):
    handle = _open_process(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        raise ProcessIdentityLabError("scratch parent process inaccessible")
    return handle


def current_process_creation_filetime_lab() -> int:
    handle = _open_identity_handle(os.getpid())
    try:
        if not _process_alive(handle):
            raise ProcessIdentityLabError("scratch parent not running")
        return _creation_filetime(handle)
    finally:
        _close_handle(handle)


class ParentProcessIdentityLab(NamedTuple):
    pid: int
    creation_filetime: int
    handle: int


def open_pinned_parent_identity_lab(pid_arg: str, creation_arg: str) -> ParentProcessIdentityLab:
    pid = _parse_pid(pid_arg)
    created = _parse_creation(creation_arg)
    if pid == os.getpid():
        raise ProcessIdentityLabError("scratch parent cannot be self")
    handle = _open_identity_handle(pid)
    try:
        if not _process_alive(handle):
            raise ProcessIdentityLabError("scratch parent already exited")
        observed = _creation_filetime(handle)
        if observed != created:
            raise ProcessIdentityLabError("scratch parent process identity mismatch")
        return ParentProcessIdentityLab(pid, observed, handle)
    except BaseException:
        _close_handle(handle)
        raise


def held_parent_still_alive_lab(identity: ParentProcessIdentityLab) -> bool:
    return _process_alive(identity.handle)


def close_parent_identity_lab(identity: ParentProcessIdentityLab) -> None:
    if not _close_handle(identity.handle):
        raise ProcessIdentityLabError("failed to close held process handle")