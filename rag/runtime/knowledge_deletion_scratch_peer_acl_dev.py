"""Read-only AccessCheck using the *actual connected client process token*.

SCRATCH DEV ONLY: no installed GUI, production pipe, authorization or ACL edits.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes

import win32api
import win32con
import win32security

from rag.runtime.knowledge_deletion_effective_accesscheck_dev import (
    _GenericMapping, _MAPPING, _access_check, _ALLOWED_MASKS,
)
from rag.runtime.knowledge_deletion_pipe_acl_inspection_dev import (
    _SE_KERNEL_OBJECT, _OWNER_SECURITY_INFORMATION,
    _DACL_SECURITY_INFORMATION, _GetSecurityInfo, _LocalFree,
)
from rag.runtime.knowledge_deletion_scratch_pipe_peer_identity_dev import (
    inspect_scratch_connected_peer_dev,
)


def inspect_scratch_connected_peer_effective_access_dev(
    server_connection, *, expected_client_pid: int,
    expected_client_birth: int | None = None, desired_access: int = 0x1
) -> dict:
    if type(desired_access) is not int or desired_access not in _ALLOWED_MASKS:
        raise ValueError("invalid FILE/PIPE specific access request")
    identity = inspect_scratch_connected_peer_dev(
        server_connection, expected_client_pid=expected_client_pid,
        expected_client_birth=expected_client_birth
    )
    result = dict(
        state="SCRATCH_PEER_ACCESSCHECK_BLOCKED",
        read_only=True, identity=identity,
        access_check_completed=False, access_granted=None,
        access_granted_mask=None, blockers=[],
        installed_gui_attested=False, installed_peer_token_attested=False,
        activation_authorized=False, operational_use_allowed=False,
        ready_for_operational_pilot=False,
    )
    if identity["state"] != "SCRATCH_KERNEL_PEER_PID_BIRTH_OBSERVED":
        result["blockers"].append("KERNEL_PEER_IDENTITY_UNVERIFIED")
        return result
    handle = server_connection._handle
    descriptor = ctypes.c_void_p()
    owner = ctypes.c_void_p()
    group = ctypes.c_void_p()
    dacl = ctypes.c_void_p()
    status = _GetSecurityInfo(
        wintypes.HANDLE(handle), _SE_KERNEL_OBJECT,
        _OWNER_SECURITY_INFORMATION | 0x00000002 | _DACL_SECURITY_INFORMATION,
        ctypes.byref(owner), ctypes.byref(group), ctypes.byref(dacl), None,
        ctypes.byref(descriptor),
    )
    if status:
        result["blockers"].append("KERNEL_DESCRIPTOR_LOOKUP_FAILED")
        return result
    try:
        if not descriptor.value or not dacl.value:
            result["blockers"].append("NULL_OR_MISSING_DACL")
            return result
        proc = win32api.OpenProcess(
            win32con.PROCESS_QUERY_LIMITED_INFORMATION, False,
            identity["observed_peer_pid"],
        )
        try:
            original = win32security.OpenProcessToken(
                proc, win32con.TOKEN_QUERY | win32con.TOKEN_DUPLICATE
            )
            try:
                impersonation = win32security.DuplicateToken(
                    original, win32security.SecurityImpersonation
                )
                try:
                    privileges = ctypes.create_string_buffer(2048)
                    privileges_size = wintypes.DWORD(len(privileges))
                    granted = wintypes.DWORD()
                    decision = wintypes.BOOL()
                    success = _access_check(
                        descriptor, wintypes.HANDLE(int(impersonation)),
                        desired_access, ctypes.byref(_MAPPING),
                        privileges, ctypes.byref(privileges_size),
                        ctypes.byref(granted), ctypes.byref(decision),
                    )
                    if not success:
                        result["blockers"].append("PEER_TOKEN_ACCESSCHECK_API_FAILED_"+str(ctypes.get_last_error()))
                        return result
                    result["access_check_completed"] = True
                    result["access_granted"] = bool(decision.value)
                    result["access_granted_mask"] = f"{granted.value:08x}"
                finally:
                    impersonation.Close()
            finally:
                original.Close()
        finally:
            proc.Close()
    except (OSError, ValueError, RuntimeError):
        result["blockers"].append("PEER_TOKEN_QUERY_FAILED")
        return result
    result["state"] = "SCRATCH_PEER_KERNEL_TOKEN_ACCESSCHECK_COMPLETE"
    if not result["access_granted"]:
        result["blockers"].append("PEER_TOKEN_ACCESS_DENIED")
    return result
