"""G-31: read-only Win32 token integrity labels (not privilege attestation)."""
from __future__ import annotations
import ctypes
from ctypes import wintypes

from rag.runtime.knowledge_deletion_child_token_observer_dev import (
    _GetCurrentProcess,_OpenProcessToken,_CloseHandle,
    _TOKEN_QUERY,_token_data,
)
_TOKEN_INTEGRITY_LEVEL=25
_adv=ctypes.WinDLL("advapi32",use_last_error=True)
_Count=_adv.GetSidSubAuthorityCount
_Count.argtypes=[ctypes.c_void_p]
_Count.restype=ctypes.POINTER(ctypes.c_ubyte)
_Sub=_adv.GetSidSubAuthority
_Sub.argtypes=[ctypes.c_void_p,wintypes.DWORD]
_Sub.restype=ctypes.POINTER(wintypes.DWORD)

def _label(token)->str:
    buf=_token_data(token,_TOKEN_INTEGRITY_LEVEL)
    sid=ctypes.c_void_p.from_buffer(buf).value
    if not sid:
        raise PermissionError("token integrity SID absent")
    count=_Count(ctypes.c_void_p(sid))
    if not count or not 1<=int(count.contents.value)<=15:
        raise PermissionError("token integrity SID subauthority invalid")
    ptr=_Sub(ctypes.c_void_p(sid),count.contents.value-1)
    if not ptr:
        raise PermissionError("token integrity RID missing")
    rid=int(ptr.contents.value)
    if rid<0x1000:return "UNTRUSTED"
    if rid<0x2000:return "LOW"
    if rid<0x3000:return "MEDIUM"
    if rid<0x4000:return "HIGH"
    if rid<0x5000:return "SYSTEM"
    return "PROTECTED_OR_UNKNOWN"

def inspect_scratch_integrity_levels_dev(child_process_handle:int)->dict:
    if type(child_process_handle) is not int or child_process_handle<=0:
        raise ValueError("child process HANDLE must be positive int")
    proof=dict(state="SCRATCH_TOKEN_INTEGRITY_UNATTESTED",
        parent_integrity=None,child_integrity=None,integrity_levels_equal=None,
        effective_acl_attested=False,privilege_isolation_attested=False,
        activation_authorized=False,operational_use_allowed=False,read_only=True)
    first=wintypes.HANDLE()
    second=wintypes.HANDLE()
    if not _OpenProcessToken(_GetCurrentProcess(),_TOKEN_QUERY,ctypes.byref(first)):
        return proof
    try:
        if not _OpenProcessToken(wintypes.HANDLE(child_process_handle),
                                 _TOKEN_QUERY,ctypes.byref(second)):
            return proof
        try:
            parent_label=_label(first)
            child_label=_label(second)
            proof.update(state="SCRATCH_TOKEN_INTEGRITY_LABELS_OBSERVED",
                parent_integrity=parent_label,child_integrity=child_label,
                integrity_levels_equal=parent_label==child_label)
        except (PermissionError,OSError,ValueError):
            return proof
        finally:
            _CloseHandle(second)
    finally:
        _CloseHandle(first)
    return proof
