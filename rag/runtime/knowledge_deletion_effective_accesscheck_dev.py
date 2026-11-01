"""Native Windows AccessCheck on a caller-owned scratch pipe, read-only.

This is development evidence only.  It neither identifies the installed GUI
nor grants any permission for operational RAG deletion.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import msvcrt
import win32api
import win32con
import win32security

from rag.runtime.knowledge_deletion_pipe_acl_inspection_dev import (
    _SE_KERNEL_OBJECT, _OWNER_SECURITY_INFORMATION,
    _DACL_SECURITY_INFORMATION, _GetSecurityInfo, _LocalFree,
)


class _GenericMapping(ctypes.Structure):
    _fields_ = [
        ("GenericRead", wintypes.DWORD),
        ("GenericWrite", wintypes.DWORD),
        ("GenericExecute", wintypes.DWORD),
        ("GenericAll", wintypes.DWORD),
    ]


_adv = ctypes.WinDLL("advapi32", use_last_error=True)
_access_check = _adv.AccessCheck
_access_check.argtypes = [
    ctypes.c_void_p, wintypes.HANDLE, wintypes.DWORD,
    ctypes.POINTER(_GenericMapping), ctypes.c_void_p,
    ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD),
    ctypes.POINTER(wintypes.BOOL),
]
_access_check.restype = wintypes.BOOL

# Explicit FILE/PIPE generic mapping; no GENERIC_* desired bits accepted.
_GROUP_SECURITY_INFORMATION = 0x00000002
_MAPPING = _GenericMapping(0x00120089, 0x00120116, 0x001200A0, 0x001F01FF)
_ALLOWED_MASKS = frozenset((0x00000001, 0x00000002, 0x00100000))


def inspect_scratch_pipe_effective_access_dev(fd: int, desired_access: int) -> dict:
    """Checks the *current process token* against an existing pipe's security.

    The input must be an open Python fd, never an arbitrary raw HANDLE.
    No privilege changes, impersonation of the installed GUI, IPC traffic,
    or security-descriptor changes are made.
    """
    if type(fd) is not int or fd < 0:
        raise ValueError("invalid pipe fd")
    if type(desired_access) is not int or desired_access not in _ALLOWED_MASKS:
        raise ValueError("unsupported specific access mask")

    result = dict(
        state="SCRATCH_ACCESSCHECK_UNVERIFIED", requested_mask_hex=f"{desired_access:08x}",
        access_check_completed=False, access_granted=None, granted_mask_hex=None,
        blockers=[], installed_gui_attested=False, peer_token_attested=False,
        ready_for_operational_pilot=False, activation_authorized=False,
        operational_use_allowed=False, read_only=True,
    )
    try:
        handle = msvcrt.get_osfhandle(fd)
    except OSError:
        result["blockers"].append("INVALID_DESCRIPTOR")
        return result

    security = ctypes.c_void_p()
    owner = ctypes.c_void_p()
    group = ctypes.c_void_p()
    dacl = ctypes.c_void_p()
    status = _GetSecurityInfo(
        wintypes.HANDLE(handle), _SE_KERNEL_OBJECT,
        _OWNER_SECURITY_INFORMATION | _DACL_SECURITY_INFORMATION | _GROUP_SECURITY_INFORMATION,
        ctypes.byref(owner), ctypes.byref(group), ctypes.byref(dacl), None,
        ctypes.byref(security),
    )
    if status:
        result["blockers"].append("SECURITY_DESCRIPTOR_READ_FAILED")
        return result
    try:
        if not dacl.value or not security.value:
            result["blockers"].append("NULL_OR_ABSENT_DACL")
            return result
        # PyHANDLE must be closed explicitly; it is not a context manager.
        process_token = win32security.OpenProcessToken(
            win32api.GetCurrentProcess(),
            win32con.TOKEN_QUERY | win32con.TOKEN_DUPLICATE,
        )
        try:
            token = win32security.DuplicateToken(
                process_token, win32security.SecurityImpersonation
            )
            try:
                buffer = ctypes.create_string_buffer(2048)
                buffer_size = wintypes.DWORD(len(buffer))
                granted = wintypes.DWORD()
                access_status = wintypes.BOOL()
                ok = _access_check(
                    security, wintypes.HANDLE(int(token)), desired_access,
                    ctypes.byref(_MAPPING), buffer,
                    ctypes.byref(buffer_size), ctypes.byref(granted),
                    ctypes.byref(access_status),
                )
                if not ok:
                    result["blockers"].append(
                        "WINDOWS_ACCESSCHECK_FAILED_" + str(ctypes.get_last_error())
                    )
                    return result
                result.update(
                    state="SCRATCH_CURRENT_TOKEN_ACCESSCHECK_COMPLETE",
                    access_check_completed=True,
                    access_granted=bool(access_status.value),
                    granted_mask_hex=f"{granted.value:08x}",
                )
            finally:
                token.Close()
        finally:
            process_token.Close()
    except (OSError, ValueError, RuntimeError):
        result["blockers"].append("TOKEN_QUERY_OR_ACCESSCHECK_FAILED")
    finally:
        if security.value:
            _LocalFree(security)
    return result
