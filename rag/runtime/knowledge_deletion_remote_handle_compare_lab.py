"""G-25: Windows same-end handle comparison across process handle tables.

Only for newly spawned, controlled scratch children. Duplicates one handle
from a caller-supplied child process into this process and compares its
kernel object to a caller-held SAME-END handle. Never an authorization for
installed GUI, RAG data, or operational deletion.
"""
from __future__ import annotations
import ctypes
from ctypes import wintypes
import msvcrt

_kernel=ctypes.WinDLL("kernel32", use_last_error=True)
_kernelbase=ctypes.WinDLL("kernelbase", use_last_error=True)
_DuplicateHandle=_kernel.DuplicateHandle
_DuplicateHandle.argtypes=[
    wintypes.HANDLE,wintypes.HANDLE,wintypes.HANDLE,
    ctypes.POINTER(wintypes.HANDLE),wintypes.DWORD,wintypes.BOOL,wintypes.DWORD,
]
_DuplicateHandle.restype=wintypes.BOOL
_GetCurrentProcess=_kernel.GetCurrentProcess
_GetCurrentProcess.argtypes=[]
_GetCurrentProcess.restype=wintypes.HANDLE
_CloseHandle=_kernel.CloseHandle
_CloseHandle.argtypes=[wintypes.HANDLE]
_CloseHandle.restype=wintypes.BOOL
_GetFileType=_kernel.GetFileType
_GetFileType.argtypes=[wintypes.HANDLE]
_GetFileType.restype=wintypes.DWORD
_CompareObjectHandles=_kernelbase.CompareObjectHandles
_CompareObjectHandles.argtypes=[wintypes.HANDLE,wintypes.HANDLE]
_CompareObjectHandles.restype=wintypes.BOOL
_DUPLICATE_SAME_ACCESS=2
_FILE_TYPE_PIPE=3

def compare_remote_same_end_pipe_handle_scratch(*,child_process_handle:int,
                                                remote_handle:int,
                                                parent_same_end_fd:int)->dict:
    if (type(child_process_handle) is not int or child_process_handle<=0
            or type(remote_handle) is not int or remote_handle<=0
            or type(parent_same_end_fd) is not int or parent_same_end_fd<0):
        raise ValueError("strict positive native handles and valid parent fd")
    receipt=dict(state="SCRATCH_REMOTE_SAME_END_UNATTESTED",
                 imported_pipe_handle=False,same_kernel_object=False,
                 child_birth_bound=False,child_pid_bound=False,
                 installed_gui_attested=False,operational_use_allowed=False,
                 activation_authorized=False,read_only=True)
    try:
        local=msvcrt.get_osfhandle(parent_same_end_fd)
    except OSError:
        return receipt
    imported=wintypes.HANDLE()
    if not _DuplicateHandle(wintypes.HANDLE(child_process_handle),
                            wintypes.HANDLE(remote_handle),_GetCurrentProcess(),
                            ctypes.byref(imported),0,False,_DUPLICATE_SAME_ACCESS):
        return receipt
    try:
        if _GetFileType(imported)!=_FILE_TYPE_PIPE or _GetFileType(local)!=_FILE_TYPE_PIPE:
            return receipt
        receipt["imported_pipe_handle"]=True
        matched=bool(_CompareObjectHandles(imported,wintypes.HANDLE(local)))
        receipt["same_kernel_object"]=matched
        receipt["state"]=("SCRATCH_REMOTE_SAME_END_MATCH" if matched
                          else "SCRATCH_REMOTE_SAME_END_MISMATCH")
        return receipt
    finally:
        _CloseHandle(imported)
