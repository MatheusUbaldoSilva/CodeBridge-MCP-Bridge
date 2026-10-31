"""DQ-E-D-3C-G-4: laboratory MAC envelope, not a channel bootstrap.

A MAC proves possession of a 256-bit session secret; it does NOT prove how
the child obtained that secret. Production transport, inherited handle ACL,
and live-process attestation are separate unimplemented security gates.
"""
from __future__ import annotations
import hashlib
import hmac
import json
import re
import secrets

_HEX64=re.compile(r"[a-f0-9]{64}\Z")

def issue_lab_secret() -> bytes:
    return secrets.token_bytes(32)

def _message(session_id:str,challenge:str,request_sha256:str,
             project_id:str,generation:str,child_pid:int) -> bytes:
    if (not isinstance(session_id,str) or not _HEX64.fullmatch(session_id)
            or not isinstance(challenge,str) or not _HEX64.fullmatch(challenge)
            or not isinstance(request_sha256,str) or not _HEX64.fullmatch(request_sha256)
            or not isinstance(project_id,str) or not project_id
            or not isinstance(generation,str) or not generation
            or type(child_pid) is not int or child_pid<=0):
        raise ValueError("invalid immutable session fields")
    return json.dumps({
        "version":1,"session":session_id,"challenge":challenge,
        "request_sha256":request_sha256,"project":project_id,
        "generation":generation,"child_pid":child_pid,
    },sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")

def sign_lab_response(secret:bytes,*,session_id:str,challenge:str,
                      request_sha256:str,project_id:str,generation:str,
                      child_pid:int)->str:
    if type(secret) is not bytes or len(secret)!=32:
        raise ValueError("lab secret must be exactly 32 bytes")
    data=_message(session_id,challenge,request_sha256,project_id,generation,child_pid)
    return hmac.new(secret,data,hashlib.sha256).hexdigest()

def verify_lab_response(secret:bytes,mac:str,*,session_id:str,challenge:str,
                        request_sha256:str,project_id:str,generation:str,
                        child_pid:int)->bool:
    if not isinstance(mac,str) or not _HEX64.fullmatch(mac):
        return False
    expected=sign_lab_response(secret,session_id=session_id,challenge=challenge,
        request_sha256=request_sha256,project_id=project_id,generation=generation,
        child_pid=child_pid)
    return hmac.compare_digest(mac,expected)


def sign_lab_birth_response(secret:bytes,*,creation_filetime:int,
                            session_id:str,challenge:str,request_sha256:str,
                            project_id:str,generation:str,child_pid:int)->str:
    if type(secret) is not bytes or len(secret)!=32:
        raise ValueError("lab secret must be exactly 32 bytes")
    if type(creation_filetime) is not int or not 0 < creation_filetime <= 0xFFFFFFFFFFFFFFFF:
        raise ValueError("invalid Win32 creation FILETIME")
    payload=_message(session_id,challenge,request_sha256,project_id,generation,child_pid)
    transcript=b"CODEBRIDGE-LAB-WIN32-BIRTH-V1\0"+payload+b"\0"+str(creation_filetime).encode("ascii")
    return hmac.new(secret,transcript,hashlib.sha256).hexdigest()


def verify_lab_birth_response(secret:bytes,mac:str,*,creation_filetime:int,
                              session_id:str,challenge:str,request_sha256:str,
                              project_id:str,generation:str,child_pid:int)->bool:
    if not isinstance(mac,str) or not _HEX64.fullmatch(mac):
        return False
    expected=sign_lab_birth_response(secret,creation_filetime=creation_filetime,
        session_id=session_id,challenge=challenge,request_sha256=request_sha256,
        project_id=project_id,generation=generation,child_pid=child_pid)
    return hmac.compare_digest(mac,expected)
