"""G-26: independent scratch Windows child, same-end kernel identity proof.

The child must remain running until parent compares its live handle table.
No real RAG workspace/index/journal is read or changed.
"""
from __future__ import annotations
import ctypes
from ctypes import wintypes
import json
import msvcrt
import os
import re
import secrets
import subprocess
import sys
import time
from rag.runtime.knowledge_deletion_parent_identity_lab import _creation_filetime
from rag.runtime.knowledge_deletion_remote_handle_compare_lab import (
    compare_remote_same_end_pipe_handle_scratch,
)

_KERNEL=ctypes.WinDLL("kernel32",use_last_error=True)
_PEEK=_KERNEL.PeekNamedPipe
_PEEK.argtypes=[wintypes.HANDLE,ctypes.c_void_p,wintypes.DWORD,
                ctypes.c_void_p,ctypes.POINTER(wintypes.DWORD),ctypes.c_void_p]
_PEEK.restype=wintypes.BOOL
_NAMES=("stdin","stdout","stderr")

def _read_scratch_line(fd:int,deadline:float)->bytes:
    buf=b""
    while time.monotonic()<deadline:
        available=wintypes.DWORD()
        if not _PEEK(wintypes.HANDLE(msvcrt.get_osfhandle(fd)),None,0,None,
                     ctypes.byref(available),None):
            raise RuntimeError("scratch child pipe unavailable")
        if available.value:
            if len(buf)+available.value>2048:
                raise RuntimeError("scratch child receipt exceeded 2048 bytes")
            buf+=os.read(fd,min(available.value,2048-len(buf)))
            if b"\n" in buf:
                if buf.count(b"\n")!=1 or not buf.endswith(b"\n"):
                    raise RuntimeError("scratch child receipt has extra data")
                return buf
        else:
            time.sleep(.01)
    raise RuntimeError("scratch child receipt timeout")

def scratch_remote_same_end_roundtrip(*,timeout_seconds:float=5.0)->dict:
    if type(timeout_seconds) not in (int,float) or not .2<=timeout_seconds<=10:
        raise ValueError("bounded scratch timeout required")
    challenge=secrets.token_hex(32)
    in_r,in_w=os.pipe()
    out_r,out_w=os.pipe()
    err_r,err_w=os.pipe()
    descriptors=[in_r,in_w,out_r,out_w,err_r,err_w]
    proc=None
    try:
        proc=subprocess.Popen(
            [sys._base_executable,"-B","-m",
             "rag.runtime.knowledge_deletion_remote_handle_child_lab"],
            stdin=in_r,stdout=out_w,stderr=err_w,close_fds=True,shell=False)
        deadline=time.monotonic()+timeout_seconds
        wire=json.dumps({"challenge":challenge,"project_id":"scratch",
                         "generation":"lab"},separators=(",",":")).encode()+b"\n"
        if os.write(in_w,wire)!=len(wire):
            raise RuntimeError("scratch challenge write incomplete")
        response=json.loads(_read_scratch_line(out_r,deadline))
        if not isinstance(response,dict) or set(response)!={"pid","birth","challenge","std_handles"}:
            raise RuntimeError("scratch child receipt malformed")
        if response["challenge"]!=challenge:
            raise RuntimeError("scratch challenge mismatch")
        if type(response["pid"]) is not int or response["pid"]!=proc.pid:
            raise RuntimeError("scratch child PID mismatch")
        if type(response["birth"]) is not int or response["birth"]!=_creation_filetime(proc._handle):
            raise RuntimeError("scratch child Win32 birth mismatch")
        received=response["std_handles"]
        if not isinstance(received,dict) or set(received)!=set(_NAMES):
            raise RuntimeError("scratch child std handle set invalid")
        matching={}
        for name,parent_fd in zip(_NAMES,(in_r,out_w,err_w)):
            evidence=compare_remote_same_end_pipe_handle_scratch(
                child_process_handle=int(proc._handle),
                remote_handle=received[name],parent_same_end_fd=parent_fd)
            if evidence["same_kernel_object"] is not True:
                raise RuntimeError("scratch child native same-end handle mismatch")
            matching[name]=True
        os.write(in_w,b"ACK\n")
        remaining=max(.1,deadline-time.monotonic())
        proc.wait(timeout=remaining)
        if proc.returncode!=0:
            raise RuntimeError("scratch child rejected ACK")
        return {
            "state":"SCRATCH_CROSS_PROCESS_SAME_END_HANDLES_MATCHED",
            "same_end_handles_match":matching,
            "child_pid_and_win32_birth_matched":True,
            "child_binary_trusted_for_production":False,
            "token_effective_acl_attested":False,
            "installation_attested":False,
            "activation_authorized":False,"operational_use_allowed":False,
            "read_only":True}
    except (subprocess.TimeoutExpired,ValueError,TypeError,KeyError) as exc:
        raise RuntimeError("scratch cross process channel invalid") from exc
    finally:
        try:
            if proc is not None and proc.poll() is None:
                proc.kill()
                proc.wait()
        finally:
            for fd in descriptors:
                os.close(fd)
