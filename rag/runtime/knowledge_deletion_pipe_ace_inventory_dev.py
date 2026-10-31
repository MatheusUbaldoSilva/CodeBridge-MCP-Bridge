"""G-18 DEV: bounded native Win32 ACE inventory for an existing pipe fd.

Observation only: does not evaluate effective token permissions, deny ordering,
restricted tokens, process privileges, or handle duplication/inheritance.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import hashlib
import msvcrt

from rag.runtime.knowledge_deletion_pipe_acl_inspection_dev import (
    _SE_KERNEL_OBJECT, _DACL_SECURITY_INFORMATION, _OWNER_SECURITY_INFORMATION,
    _GetSecurityInfo, _LocalFree,
)

_ADV=ctypes.WinDLL("advapi32",use_last_error=True)
_GetAclInformation=_ADV.GetAclInformation
_GetAclInformation.argtypes=[ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD]
_GetAclInformation.restype=wintypes.BOOL
_GetAce=_ADV.GetAce
_GetAce.argtypes=[ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(ctypes.c_void_p)]
_GetAce.restype=wintypes.BOOL
_IsValidSid=_ADV.IsValidSid
_IsValidSid.argtypes=[ctypes.c_void_p]
_IsValidSid.restype=wintypes.BOOL
_ConvertSid=_ADV.ConvertSidToStringSidW
_ConvertSid.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_wchar_p)]
_ConvertSid.restype=wintypes.BOOL

class _AclSizeInformation(ctypes.Structure):
    _fields_=[("AceCount",wintypes.DWORD),
              ("AclBytesInUse",wintypes.DWORD),
              ("AclBytesFree",wintypes.DWORD)]
class _AceHeader(ctypes.Structure):
    _fields_=[("AceType",ctypes.c_ubyte),("AceFlags",ctypes.c_ubyte),
              ("AceSize",ctypes.c_ushort)]

_BROAD={
    "S-1-1-0":"EVERYONE",
    "S-1-5-11":"AUTHENTICATED_USERS",
    "S-1-5-7":"ANONYMOUS_LOGON",
    "S-1-5-32-545":"BUILTIN_USERS",
    "S-1-5-2":"NETWORK",
}
_MAX_ACE_COUNT=64
_MAX_ACL_BYTES=16384
_SIMPLE_ACE_TYPES={0:"ALLOW",1:"DENY"}

def _sid_label(sid_pointer:int)->dict:
    if not _IsValidSid(ctypes.c_void_p(sid_pointer)):
        raise ValueError("ACE invalid SID")
    output=ctypes.c_wchar_p()
    if not _ConvertSid(ctypes.c_void_p(sid_pointer),ctypes.byref(output)):
        raise ValueError("ACE SID string conversion failed")
    try:
        sid=output.value
        if not isinstance(sid,str) or not sid:
            raise ValueError("ACE SID text invalid")
        return {"principal_class":_BROAD.get(sid,"OTHER_PRINCIPAL"),
                "sid_sha256":hashlib.sha256(sid.encode("ascii")).hexdigest()}
    finally:
        _LocalFree(ctypes.cast(output,ctypes.c_void_p))

def inspect_pipe_allow_aces_read_only_dev(fd:int)->dict:
    if type(fd) is not int or fd<0:
        raise ValueError("invalid pipe fd")
    result={"state":"WIN32_PIPE_ACE_INVENTORY_BLOCKED",
            "ace_count":None,"aces":[],"broad_allow_ace_detected":False,
            "unsupported_ace_detected":False,"dacl_observed":False,
            "private_acl_attested":False,"effective_access_attested":False,
            "child_handle_inheritance_attested":False,
            "activation_authorized":False,"operational_use_allowed":False,
            "read_only":True}
    try:
        handle=msvcrt.get_osfhandle(fd)
    except OSError:
        result["blockers"]=["INVALID_DESCRIPTOR"]
        return result
    owner=ctypes.c_void_p()
    dacl=ctypes.c_void_p()
    security=ctypes.c_void_p()
    status=_GetSecurityInfo(wintypes.HANDLE(handle),_SE_KERNEL_OBJECT,
        _OWNER_SECURITY_INFORMATION|_DACL_SECURITY_INFORMATION,
        ctypes.byref(owner),None,ctypes.byref(dacl),None,ctypes.byref(security))
    if status!=0:
        result["blockers"]=["WIN32_SECURITY_QUERY_FAILED"]
        return result
    try:
        if not dacl.value:
            result["blockers"]=["NULL_OR_ABSENT_DACL"]
            return result
        info=_AclSizeInformation()
        if not _GetAclInformation(dacl,ctypes.byref(info),
                                  ctypes.sizeof(info),2):
            result["blockers"]=["ACL_SIZE_QUERY_FAILED"]
            return result
        count=int(info.AceCount)
        result["ace_count"]=count
        if count>_MAX_ACE_COUNT or int(info.AclBytesInUse)>_MAX_ACL_BYTES:
            result["blockers"]=["ACL_INVENTORY_LIMIT_EXCEEDED"]
            return result
        result["dacl_observed"]=True
        for index in range(count):
            pointer=ctypes.c_void_p()
            if not _GetAce(dacl,index,ctypes.byref(pointer)) or not pointer.value:
                raise ValueError("ACE read failed")
            header=_AceHeader.from_address(pointer.value)
            ace_type=int(header.AceType)
            if ace_type not in _SIMPLE_ACE_TYPES or header.AceSize < 16:
                result["unsupported_ace_detected"]=True
                result["aces"].append({"ace_type":"UNSUPPORTED"})
                continue
            mask=int(ctypes.c_uint32.from_address(
                pointer.value+ctypes.sizeof(_AceHeader)).value)
            sid_info=_sid_label(pointer.value+8)
            ace={"ace_type":_SIMPLE_ACE_TYPES[ace_type],
                 "access_mask_hex":f"{mask:08x}",
                 "principal_class":sid_info["principal_class"],
                 "sid_sha256":sid_info["sid_sha256"]}
            result["aces"].append(ace)
            if ace_type==0 and sid_info["principal_class"] in _BROAD.values():
                result["broad_allow_ace_detected"]=True
        result["state"]="WIN32_PIPE_ACE_INVENTORY_READ_ONLY"
        result["blockers"]=[]
    except (ValueError,OSError):
        result["state"]="WIN32_PIPE_ACE_INVENTORY_BLOCKED"
        result["blockers"]=["ACE_DECODE_FAILED"]
        result["aces"]=[]
    finally:
        if security.value:
            _LocalFree(security)
    return result
