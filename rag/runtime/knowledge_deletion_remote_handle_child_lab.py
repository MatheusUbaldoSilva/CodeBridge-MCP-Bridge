"""G-26: scratch child reports actual Win32 std handle values while alive.

Only responds to a strict scratch handshake, touches no RAG model/index.
"""
from __future__ import annotations
import ctypes
from ctypes import wintypes
import json
import os
import re
import sys
from rag.runtime.knowledge_deletion_child_stdio_lab import assert_scratch_stdio_pipes_win32
from rag.runtime.knowledge_deletion_remote_handle_mac_lab import sign_remote_handle_lab
from rag.runtime.knowledge_deletion_parent_identity_lab import current_process_creation_filetime_lab

_KERNEL=ctypes.WinDLL("kernel32",use_last_error=True)
_GetStdHandle=_KERNEL.GetStdHandle
_GetStdHandle.argtypes=[wintypes.DWORD]
_GetStdHandle.restype=wintypes.HANDLE
_NAMES={"stdin":0xFFFFFFF6,"stdout":0xFFFFFFF5,"stderr":0xFFFFFFF4}
_CHALLENGE=re.compile(r"[0-9a-f]{64}\Z")

def main()->int:
    try:
        assert_scratch_stdio_pipes_win32()
        raw=sys.stdin.buffer.readline(1025)
        if len(raw)>1024 or not raw:
            return 2
        request=json.loads(raw)
        if (not isinstance(request,dict)
            or set(request)!={"challenge","session_id","secret","project_id","generation"}
            or request["project_id"]!="scratch" or request["generation"]!="lab"
            or any(not isinstance(request[key],str) or not _CHALLENGE.fullmatch(request[key])
                   for key in ("challenge","session_id","secret"))):
            return 2
        secret=bytes.fromhex(request["secret"])
        receipt={"pid":os.getpid(),
            "birth":current_process_creation_filetime_lab(),
            "challenge":request["challenge"],
            "std_handles":{name:int(_GetStdHandle(code)) for name,code in _NAMES.items()}}
        receipt["mac"]=sign_remote_handle_lab(secret,
            session_id=request["session_id"],challenge=receipt["challenge"],
            project_id="scratch",generation="lab",child_pid=receipt["pid"],
            creation_filetime=receipt["birth"],std_handles=receipt["std_handles"])
        print(json.dumps(receipt,sort_keys=True,separators=(",",":")),flush=True)
        ack=sys.stdin.buffer.readline(1025)
        if ack!=b"ACK\n":
            return 2
        return 0
    except (ValueError,TypeError,KeyError,OverflowError,UnicodeError):
        return 2

if __name__=="__main__":
    raise SystemExit(main())
