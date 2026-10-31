"""G-20: read-only native Win32 std-handle descriptor receipt.

Same SDDL digest does NOT uniquely identify a pipe kernel object; it only
confirms matching observable security-descriptor content.
"""
from __future__ import annotations
import ctypes
from ctypes import wintypes
import hashlib

from rag.runtime.knowledge_deletion_pipe_acl_inspection_dev import (
    _GetSecurityInfo,_Convert,_LocalFree,_OWNER_SECURITY_INFORMATION,
    _DACL_SECURITY_INFORMATION,_SE_KERNEL_OBJECT,_REVISION,
)

_kernel=ctypes.WinDLL("kernel32",use_last_error=True)
_GetStdHandle=_kernel.GetStdHandle
_GetStdHandle.argtypes=[wintypes.DWORD]
_GetStdHandle.restype=wintypes.HANDLE
_GetFileType=_kernel.GetFileType
_GetFileType.argtypes=[wintypes.HANDLE]
_GetFileType.restype=wintypes.DWORD
_GetHandleInformation=_kernel.GetHandleInformation
_GetHandleInformation.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)]
_GetHandleInformation.restype=wintypes.BOOL
_INPUT=0xFFFFFFF6
_OUTPUT=0xFFFFFFF5
_ERROR=0xFFFFFFF4
_FILE_TYPE_PIPE=3

def inspect_native_std_handle_receipts_lab()->dict:
    receipts={}
    for name,constant in (("stdin",_INPUT),("stdout",_OUTPUT),("stderr",_ERROR)):
        native=_GetStdHandle(constant)
        if not native or native==ctypes.c_void_p(-1).value:
            raise PermissionError("scratch std handle absent")
        if _GetFileType(native)!=_FILE_TYPE_PIPE:
            raise PermissionError("scratch std handle not pipe")
        flags=wintypes.DWORD()
        if not _GetHandleInformation(native,ctypes.byref(flags)):
            raise PermissionError("scratch std handle metadata unavailable")
        owner=ctypes.c_void_p()
        dacl=ctypes.c_void_p()
        descriptor=ctypes.c_void_p()
        result=_GetSecurityInfo(native,_SE_KERNEL_OBJECT,
           _OWNER_SECURITY_INFORMATION|_DACL_SECURITY_INFORMATION,
           ctypes.byref(owner),None,ctypes.byref(dacl),None,
           ctypes.byref(descriptor))
        if result:
            raise PermissionError("scratch std handle descriptor inaccessible")
        try:
            if not owner.value or not dacl.value:
                raise PermissionError("scratch std handle DACL or owner missing")
            out=ctypes.c_wchar_p()
            length=wintypes.ULONG()
            if not _Convert(descriptor,_REVISION,
                            _OWNER_SECURITY_INFORMATION|_DACL_SECURITY_INFORMATION,
                            ctypes.byref(out),ctypes.byref(length)):
                raise PermissionError("scratch std handle SDDL conversion refused")
            try:
                if not out.value:
                    raise PermissionError("scratch std handle descriptor empty")
                receipts[name]=dict(
                    descriptor_sha256=hashlib.sha256(out.value.encode("utf-8")).hexdigest(),
                    type="PIPE",inheritable=bool(flags.value&1))
            finally:
                _LocalFree(ctypes.cast(out,ctypes.c_void_p))
        finally:
            if descriptor.value:
                _LocalFree(descriptor)
    return dict(state="SCRATCH_CHILD_STD_DESCRIPTOR_RECEIPTS_ONLY",
                receipts=receipts,
                kernel_object_identity_attested=False,
                acl_effective_access_attested=False,
                activation_authorized=False,operational_use_allowed=False,
                read_only=True)
