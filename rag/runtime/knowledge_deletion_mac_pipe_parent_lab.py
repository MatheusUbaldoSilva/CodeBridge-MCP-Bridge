"""DQ-E-D-3C-G-5: bounded anonymous-pipe MAC lab handshake.

This is NOT an authenticated production channel and does NOT grant RAG access.
Secret is transmitted only via an ephemeral stdin pipe, never via argv/env/disk.
"""
from __future__ import annotations
import json
import re
import secrets
import subprocess
import sys
from rag.runtime.knowledge_deletion_channel_mac_lab import (
    issue_lab_secret, verify_lab_response,
)

def scratch_mac_pipe_roundtrip(*,project_id="scratch",generation="lab",
                               timeout_seconds:float=5.0)->dict:
    if (project_id!="scratch" or generation!="lab"
            or type(timeout_seconds) not in (int,float)
            or not 0.1 <= timeout_seconds <= 10.0):
        raise ValueError("strict scratch only")
    key=issue_lab_secret()
    fields={"session_id":secrets.token_hex(32),"challenge":secrets.token_hex(32),
            "request_sha256":secrets.token_hex(32),"project_id":project_id,
            "generation":generation}
    wire=json.dumps({"secret":key.hex(),**fields},
                     sort_keys=True,separators=(",",":")).encode("utf-8")+b"\n"
    proc=subprocess.Popen(
        [sys.executable,"-B","-m","rag.runtime.knowledge_deletion_mac_child_lab"],
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
        close_fds=True, shell=False,
    )
    try:
        try:
            stdout,stderr=proc.communicate(input=wire,timeout=timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            proc.kill()
            proc.communicate()
            raise RuntimeError("scratch child timeout") from exc
        if proc.returncode!=0 or stderr or len(stdout)>1024:
            raise RuntimeError("scratch child blocked")
        response=json.loads(stdout)
        if not isinstance(response,dict) or set(response)!={"pid","mac"}:
            raise RuntimeError("scratch response malformed")
        pid=response["pid"]
        if type(pid) is not int or pid<=0:
            raise RuntimeError("scratch process PID invalid")
        if not verify_lab_response(key,response["mac"],**fields,child_pid=pid):
            raise RuntimeError("scratch MAC mismatch")
        return {
            "state":"SCRATCH_MAC_PIPE_ROUNDTRIP_ONLY",
            "child_reported_pid":pid,
            "mac_verified":True,
            "os_process_identity_attested":False,
            "secure_handle_acl_attested":False,
            "activation_authorized":False,
            "operational_use_allowed":False,
            "read_only":True,
        }
    except (ValueError,TypeError,KeyError) as exc:
        raise RuntimeError("scratch channel invalid") from exc
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
