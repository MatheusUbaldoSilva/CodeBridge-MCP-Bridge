"""G-23 Windows kernel object identity comparer for already-open scratch fds.

Win32 anonymous pipe read/write ends represent DIFFERENT file objects.
A same-object comparison is meaningful for duplicated handles of one end,
but cannot authenticate cross-end parent/child pipe channel by itself.
"""
from __future__ import annotations
import ctypes
from ctypes import wintypes
import msvcrt

_KERNEL_BASE=ctypes.WinDLL("kernelbase",use_last_error=True)
_COMPARE=getattr(_KERNEL_BASE,"CompareObjectHandles",None)
if _COMPARE is not None:
    _COMPARE.argtypes=[wintypes.HANDLE,wintypes.HANDLE]
    _COMPARE.restype=wintypes.BOOL

def compare_open_fd_objects_win32_dev(left_fd:int,right_fd:int)->dict:
    if type(left_fd) is not int or left_fd<0 or type(right_fd) is not int or right_fd<0:
        raise ValueError("two live nonnegative fds required")
    evidence=dict(state="SCRATCH_HANDLE_IDENTITY_NOT_ATTESTED",
        same_kernel_object=None,compare_api_available=(_COMPARE is not None),
        cross_process_inheritance_attested=False,
        operational_use_allowed=False,activation_authorized=False,
        read_only=True)
    if _COMPARE is None:
        return evidence
    try:
        first=msvcrt.get_osfhandle(left_fd)
        second=msvcrt.get_osfhandle(right_fd)
    except OSError:
        return evidence
    # Native call only compares existing handle identities; no duplication,
    # access-control change, handle creation, or transfer is performed here.
    matched=bool(_COMPARE(wintypes.HANDLE(first),wintypes.HANDLE(second)))
    evidence["same_kernel_object"]=matched
    evidence["state"]="SCRATCH_KERNEL_OBJECT_COMPARISON_OBSERVED"
    return evidence
