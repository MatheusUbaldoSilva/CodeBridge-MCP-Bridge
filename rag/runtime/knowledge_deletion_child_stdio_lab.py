"""G-16 synthetic child-side Win32 std-handle type guard (SCRATCH ONLY).

Checks the child's OWN GetStdHandle descriptors, not a claim from its parent.
Does not prove ACL restrictiveness, process ownership or production security.
"""
from __future__ import annotations
import ctypes
from ctypes import wintypes

_KERNEL=ctypes.WinDLL("kernel32",use_last_error=True)
_GET_STD=_KERNEL.GetStdHandle
_GET_STD.argtypes=[wintypes.DWORD]
_GET_STD.restype=wintypes.HANDLE
_GET_TYPE=_KERNEL.GetFileType
_GET_TYPE.argtypes=[wintypes.HANDLE]
_GET_TYPE.restype=wintypes.DWORD
_STD=(0xFFFFFFF6,0xFFFFFFF5,0xFFFFFFF4)  # STD_INPUT/OUTPUT/ERROR
_FILE_TYPE_PIPE=0x0003

def assert_scratch_stdio_pipes_win32()->dict:
    for which in _STD:
        handle=_GET_STD(which)
        if not handle or handle==ctypes.c_void_p(-1).value:
            raise PermissionError("scratch std handle invalid")
        if _GET_TYPE(handle)!=_FILE_TYPE_PIPE:
            raise PermissionError("scratch std handle is not a pipe")
    return dict(state="SCRATCH_CHILD_WIN32_STDIO_PIPE_TYPES_OBSERVED",
        three_pipe_types_observed=True,
        child_acl_trusted=False,
        inherited_handle_identity_attested=False,
        activation_authorized=False,operational_use_allowed=False,read_only=True)
