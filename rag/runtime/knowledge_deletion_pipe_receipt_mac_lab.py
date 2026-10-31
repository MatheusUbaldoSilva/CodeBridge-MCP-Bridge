"""G-21: domain-separated MAC for Win32 scratch stdio descriptor receipts.

Descriptor SHA256 equality is NOT an OS kernel-object identity proof.
"""
from __future__ import annotations
import hashlib
import hmac
import json
import re

from rag.runtime.knowledge_deletion_channel_mac_lab import _message

_SHA=re.compile(r"[0-9a-f]{64}\Z")
_PIPES=frozenset(("stdin","stdout","stderr"))
_DOMAIN=b"CODEBRIDGE-SCRATCH-STDIO-RECEIPTS-V2\0"

def _receipt_message(*,session_id:str,challenge:str,request_sha256:str,
                     project_id:str,generation:str,child_pid:int,
                     creation_filetime:int,stdio_receipts:dict)->bytes:
    if type(creation_filetime) is not int or not 0<creation_filetime<=0xFFFFFFFFFFFFFFFF:
        raise ValueError("invalid Win32 FILETIME")
    if not isinstance(stdio_receipts,dict) or set(stdio_receipts)!=_PIPES:
        raise ValueError("exact three stdio receipt digests required")
    for value in stdio_receipts.values():
        if not isinstance(value,str) or not _SHA.fullmatch(value):
            raise ValueError("noncanonical stdio descriptor SHA256")
    base=_message(session_id,challenge,request_sha256,
                  project_id,generation,child_pid)
    suffix=json.dumps({"birth_filetime":creation_filetime,
                       "stdio_receipts":stdio_receipts},
                       separators=(",",":"),sort_keys=True,
                       ensure_ascii=True).encode("ascii")
    return _DOMAIN+base+b"\0"+suffix

def sign_lab_stdio_receipts(secret:bytes,*,session_id:str,challenge:str,
                           request_sha256:str,project_id:str,generation:str,
                           child_pid:int,creation_filetime:int,
                           stdio_receipts:dict)->str:
    if type(secret) is not bytes or len(secret)!=32:
        raise ValueError("scratch session secret must be exactly 256 bits")
    message=_receipt_message(session_id=session_id,challenge=challenge,
        request_sha256=request_sha256,project_id=project_id,
        generation=generation,child_pid=child_pid,
        creation_filetime=creation_filetime,stdio_receipts=stdio_receipts)
    return hmac.new(secret,message,hashlib.sha256).hexdigest()

def verify_lab_stdio_receipts(secret:bytes,mac:str,*,session_id:str,
                             challenge:str,request_sha256:str,
                             project_id:str,generation:str,child_pid:int,
                             creation_filetime:int,stdio_receipts:dict)->bool:
    if not isinstance(mac,str) or not _SHA.fullmatch(mac):
        return False
    target=sign_lab_stdio_receipts(secret,session_id=session_id,
        challenge=challenge,request_sha256=request_sha256,
        project_id=project_id,generation=generation,child_pid=child_pid,
        creation_filetime=creation_filetime,stdio_receipts=stdio_receipts)
    return hmac.compare_digest(mac,target)
