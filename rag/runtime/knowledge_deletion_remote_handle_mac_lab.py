"""G-27: scratch-only MAC over process birth and native child std handles."""
from __future__ import annotations
import hashlib
import hmac
import json
import re

_HEX64=re.compile(r"[0-9a-f]{64}\Z")
_NAMES=frozenset(("stdin","stdout","stderr"))
_DOMAIN=b"CODEBRIDGE-G27-REMOTE-SAME-END-SCRATCH-V1\0"

def _message(*,session_id:str,challenge:str,project_id:str,generation:str,
             child_pid:int,creation_filetime:int,std_handles:dict)->bytes:
    if project_id!="scratch" or generation!="lab":
        raise ValueError("scratch only")
    if any(type(x) is not str or not _HEX64.fullmatch(x)
           for x in (session_id,challenge)):
        raise ValueError("malformed session or challenge")
    if (type(child_pid) is not int or not 0<child_pid<=0xFFFFFFFF
            or type(creation_filetime) is not int
            or not 0<creation_filetime<=0xFFFFFFFFFFFFFFFF):
        raise ValueError("invalid process identity")
    if not isinstance(std_handles,dict) or set(std_handles)!=_NAMES:
        raise ValueError("exact three native child handles required")
    for name,handle in std_handles.items():
        if type(handle) is not int or not 0<handle<=0xFFFFFFFFFFFFFFFF:
            raise ValueError("invalid native handle")
    canonical=json.dumps(dict(
        session_id=session_id,challenge=challenge,project_id=project_id,
        generation=generation,child_pid=child_pid,
        creation_filetime=creation_filetime,std_handles=std_handles),
        sort_keys=True,ensure_ascii=True,separators=(",",":")).encode("ascii")
    return _DOMAIN+canonical

def sign_remote_handle_lab(secret:bytes,**kwargs)->str:
    if type(secret) is not bytes or len(secret)!=32:
        raise ValueError("scratch key must be 32 bytes")
    return hmac.new(secret,_message(**kwargs),hashlib.sha256).hexdigest()

def verify_remote_handle_lab(secret:bytes,signature:str,**kwargs)->bool:
    if not isinstance(signature,str) or not _HEX64.fullmatch(signature):
        return False
    expected=sign_remote_handle_lab(secret,**kwargs)
    return hmac.compare_digest(expected,signature)
