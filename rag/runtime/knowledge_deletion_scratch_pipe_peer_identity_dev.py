"""DEV-only OS kernel peer PID/birth-time evidence for a caller-owned scratch pipe.

This helper is deliberately NOT wired to the installed GUI or operational IPC.
Kernel peer PID is stronger than a payload claim, but this does not establish
loaded GUI code identity, process token effective authorization, or G32.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes

import win32api
import win32con
import win32process
import win32security

_kernel = ctypes.WinDLL("kernel32", use_last_error=True)
_client_pid = _kernel.GetNamedPipeClientProcessId
_client_pid.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.ULONG)]
_client_pid.restype = wintypes.BOOL
_client_session = _kernel.GetNamedPipeClientSessionId
_client_session.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.ULONG)]
_client_session.restype = wintypes.BOOL


def inspect_scratch_connected_peer_dev(
    server_connection, *, expected_client_pid: int, expected_client_birth: int | None = None
) -> dict:
    """Peer is read from kernel, not from an untrusted protocol message."""
    if type(expected_client_pid) is not int or expected_client_pid <= 0:
        raise ValueError("expected PID required")
    if expected_client_birth is not None and (
        type(expected_client_birth) is not int or expected_client_birth <= 0
    ):
        raise ValueError("invalid birth receipt")
    result = dict(
        state="SCRATCH_PEER_NOT_VERIFIED", read_only=True,
        observed_peer_pid=None, peer_session=None, observed_birth=None,
        expected_pid_matches=False, expected_birth_matches=False,
        same_operator_user=False, blockers=[],
        installed_gui_attested=False, installed_peer_token_attested=False,
        activation_authorized=False, operational_use_allowed=False,
        ready_for_operational_pilot=False,
    )
    handle = getattr(server_connection, "_handle", None)
    if handle is None or getattr(server_connection, "_server_side", False) is not True:
        result["blockers"].append("NOT_SERVER_SIDE_CONNECTED_PIPE")
        return result
    pid = wintypes.ULONG(0)
    session = wintypes.ULONG(0)
    if not _client_pid(handle, ctypes.byref(pid)) or not _client_session(
        handle, ctypes.byref(session)
    ):
        result["blockers"].append("KERNEL_PEER_LOOKUP_FAILED")
        return result
    result["observed_peer_pid"] = pid.value
    result["peer_session"] = session.value
    result["expected_pid_matches"] = pid.value == expected_client_pid
    try:
        proc = win32api.OpenProcess(win32con.PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        try:
            birth = int(win32process.GetProcessTimes(proc)["CreationTime"].timestamp() * 1_000_000)
            result["observed_birth"] = birth
            result["expected_birth_matches"] = (
                expected_client_birth is None or birth == expected_client_birth
            )
            token = win32security.OpenProcessToken(proc, win32security.TOKEN_QUERY)
            try:
                peer_sid = win32security.GetTokenInformation(token, win32security.TokenUser)[0]
                current = win32security.OpenProcessToken(
                    win32api.GetCurrentProcess(), win32security.TOKEN_QUERY
                )
                try:
                    user_sid = win32security.GetTokenInformation(
                        current, win32security.TokenUser
                    )[0]
                    result["same_operator_user"] = bool(
                        win32security.ConvertSidToStringSid(peer_sid)
                        == win32security.ConvertSidToStringSid(user_sid)
                    )
                finally:
                    current.Close()
            finally:
                token.Close()
        finally:
            proc.Close()
    except (OSError, ValueError, KeyError) as exc:
        result["blockers"].append("PROCESS_TOKEN_OR_BIRTH_QUERY_FAILED")
        return result
    if not result["expected_pid_matches"]:
        result["blockers"].append("PEER_PID_MISMATCH")
    if not result["expected_birth_matches"]:
        result["blockers"].append("PEER_BIRTH_MISMATCH")
    if not result["same_operator_user"]:
        result["blockers"].append("PEER_USER_MISMATCH")
    if not result["blockers"]:
        result["state"] = "SCRATCH_KERNEL_PEER_PID_BIRTH_OBSERVED"
    return result
