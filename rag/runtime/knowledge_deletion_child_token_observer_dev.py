"""G-29: read-only Win32 parent/child token SID comparison.

Does not disclose account SID, privileges or token secrets. Same SID does
not prove effective rights; distinct SIDs do not prove process isolation.
"""
from __future__ import annotations
import ctypes
from ctypes import wintypes

_adv=ctypes.WinDLL("advapi32",use_last_error=True)
_ker=ctypes.WinDLL("kernel32",use_last_error=True)
_OpenProcessToken=_adv.OpenProcessToken
_OpenProcessToken.argtypes=[wintypes.HANDLE,wintypes.DWORD,ctypes.POINTER(wintypes.HANDLE)]
_OpenProcessToken.restype=wintypes.BOOL
_GetTokenInformation=_adv.GetTokenInformation
_GetTokenInformation.argtypes=[wintypes.HANDLE,wintypes.DWORD,ctypes.c_void_p,
                               wintypes.DWORD,ctypes.POINTER(wintypes.DWORD)]
_GetTokenInformation.restype=wintypes.BOOL
_EqualSid=_adv.EqualSid
_EqualSid.argtypes=[ctypes.c_void_p,ctypes.c_void_p]
_EqualSid.restype=wintypes.BOOL
_CloseHandle=_ker.CloseHandle
_CloseHandle.argtypes=[wintypes.HANDLE]
_CloseHandle.restype=wintypes.BOOL
_GetCurrentProcess=_ker.GetCurrentProcess
_GetCurrentProcess.argtypes=[]
_GetCurrentProcess.restype=wintypes.HANDLE
_TOKEN_QUERY=0x0008
_TOKEN_USER=1
_TOKEN_IS_APP_CONTAINER=29

def _token_data(handle,kind:int):
    required=wintypes.DWORD()
    _GetTokenInformation(handle,kind,None,0,ctypes.byref(required))
    if required.value<=0 or required.value>65536:
        raise PermissionError("Win32 token response size invalid")
    buf=ctypes.create_string_buffer(required.value)
    if not _GetTokenInformation(handle,kind,buf,len(buf),ctypes.byref(required)):
        raise PermissionError("Win32 token query failed")
    return buf

def inspect_child_token_identity_scratch(child_process_handle:int)->dict:
    if type(child_process_handle) is not int or child_process_handle<=0:
        raise ValueError("live child process HANDLE required")
    result=dict(state="SCRATCH_CHILD_TOKEN_UNATTESTED",
                child_token_inspected=False,
                parent_child_account_sid_equal=None,
                child_appcontainer=None,
                effective_token_isolation_attested=False,
                effective_acl_attested=False,
                activation_authorized=False,operational_use_allowed=False,read_only=True)
    first=wintypes.HANDLE()
    second=wintypes.HANDLE()
    if not _OpenProcessToken(_GetCurrentProcess(),_TOKEN_QUERY,ctypes.byref(first)):
        return result
    try:
        if not _OpenProcessToken(wintypes.HANDLE(child_process_handle),_TOKEN_QUERY,
                                 ctypes.byref(second)):
            return result
        try:
            parent_user=_token_data(first,_TOKEN_USER)
            child_user=_token_data(second,_TOKEN_USER)
            parent_sid=ctypes.c_void_p.from_buffer(parent_user).value
            child_sid=ctypes.c_void_p.from_buffer(child_user).value
            if not parent_sid or not child_sid:
                raise PermissionError("Win32 token SID absent")
            same=bool(_EqualSid(ctypes.c_void_p(parent_sid),ctypes.c_void_p(child_sid)))
            appbuf=_token_data(second,_TOKEN_IS_APP_CONTAINER)
            app=bool(ctypes.c_uint32.from_buffer(appbuf).value)
            result.update(state="SCRATCH_TOKEN_SID_LINEAGE_OBSERVED",
                child_token_inspected=True,
                parent_child_account_sid_equal=same,
                child_appcontainer=app)
        except (PermissionError,ValueError,TypeError):
            result["state"]="SCRATCH_CHILD_TOKEN_UNATTESTED"
        finally:
            _CloseHandle(second)
    finally:
        _CloseHandle(first)
    return result
