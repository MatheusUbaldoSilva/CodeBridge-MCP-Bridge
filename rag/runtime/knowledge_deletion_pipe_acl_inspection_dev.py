"""DEV-ONLY read-only Win32 security descriptor observation for anonymous pipes.

Inspects kernel security descriptor without changing ACLs or granting authority.
Even a seemingly private DACL does not attest inherited child handles.
"""
from __future__ import annotations
import ctypes
from ctypes import wintypes
import hashlib
import msvcrt

_SE_KERNEL_OBJECT=6
_OWNER_SECURITY_INFORMATION=0x00000001
_DACL_SECURITY_INFORMATION=0x00000004
_REVISION=1

_advapi=ctypes.WinDLL("advapi32",use_last_error=True)
_kernel=ctypes.WinDLL("kernel32",use_last_error=True)
_GetSecurityInfo=_advapi.GetSecurityInfo
_GetSecurityInfo.argtypes=[wintypes.HANDLE,wintypes.DWORD,wintypes.DWORD,
    ctypes.POINTER(ctypes.c_void_p),ctypes.c_void_p,ctypes.POINTER(ctypes.c_void_p),
    ctypes.c_void_p,ctypes.POINTER(ctypes.c_void_p)]
_GetSecurityInfo.restype=wintypes.DWORD
_Convert=_advapi.ConvertSecurityDescriptorToStringSecurityDescriptorW
_Convert.argtypes=[ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,
    ctypes.POINTER(ctypes.c_wchar_p),ctypes.POINTER(wintypes.ULONG)]
_Convert.restype=wintypes.BOOL
_LocalFree=_kernel.LocalFree
_LocalFree.argtypes=[ctypes.c_void_p]
_LocalFree.restype=ctypes.c_void_p
_GetHandleInformation=_kernel.GetHandleInformation
_GetHandleInformation.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)]
_GetHandleInformation.restype=wintypes.BOOL
_HANDLE_FLAG_INHERIT=0x00000001

def inspect_pipe_fd_acl_dev(fd:int)->dict:
    if type(fd) is not int or fd<0:
        raise ValueError("file descriptor must be a non-negative integer")
    result={"state":"WIN32_PIPE_ACL_UNATTESTED","descriptor_observed":False,
        "dacl_present":False,"owner_present":False,"descriptor_digest":None,
        "parent_handle_inheritable":None,
        "private_acl_attested":False,"child_handle_inheritance_attested":False,
        "activation_authorized":False,"operational_use_allowed":False,
        "read_only":True}
    try:
        handle=msvcrt.get_osfhandle(fd)
    except OSError:
        result["error_code"]="INVALID_FILE_DESCRIPTOR"
        return result
    flags=wintypes.DWORD()
    if _GetHandleInformation(wintypes.HANDLE(handle),ctypes.byref(flags)):
        result["parent_handle_inheritable"]=bool(flags.value&_HANDLE_FLAG_INHERIT)
    owner=ctypes.c_void_p()
    dacl=ctypes.c_void_p()
    descriptor=ctypes.c_void_p()
    status=_GetSecurityInfo(wintypes.HANDLE(handle),_SE_KERNEL_OBJECT,
         _OWNER_SECURITY_INFORMATION|_DACL_SECURITY_INFORMATION,
         ctypes.byref(owner),None,ctypes.byref(dacl),None,ctypes.byref(descriptor))
    if status!=0:
        result["error_code"]=int(status)
        return result
    try:
        output=ctypes.c_wchar_p()
        length=wintypes.ULONG()
        if not _Convert(descriptor,_REVISION,_OWNER_SECURITY_INFORMATION|
                        _DACL_SECURITY_INFORMATION,ctypes.byref(output),
                        ctypes.byref(length)):
            result["error_code"]=int(ctypes.get_last_error())
            return result
        try:
            sddl=output.value or ""
            result.update(descriptor_observed=True,dacl_present=bool(dacl),
                owner_present=bool(owner),
                descriptor_digest=hashlib.sha256(sddl.encode("utf-8")).hexdigest(),
                state="WIN32_PIPE_ACL_SOURCE_OBSERVED_READ_ONLY")
        finally:
            _LocalFree(ctypes.cast(output,ctypes.c_void_p))
    finally:
        if descriptor.value:
            _LocalFree(descriptor)
    return result
