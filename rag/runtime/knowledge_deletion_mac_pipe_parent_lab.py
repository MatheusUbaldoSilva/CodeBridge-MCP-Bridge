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
from rag.runtime.knowledge_deletion_parent_identity_lab import _creation_filetime
from rag.runtime.knowledge_deletion_pipe_acl_inspection_dev import inspect_pipe_fd_acl_dev
from rag.runtime.knowledge_deletion_pipe_ace_inventory_dev import inspect_pipe_allow_aces_read_only_dev
from rag.runtime.knowledge_deletion_channel_mac_lab import (
    issue_lab_secret, verify_lab_birth_response,
)

def scratch_mac_pipe_roundtrip(*,project_id="scratch",generation="lab",
                               timeout_seconds:float=5.0,entrypoint:str="synthetic")->dict:
    if (project_id!="scratch" or generation!="lab"
            or type(timeout_seconds) not in (int,float)
            or not 0.1 <= timeout_seconds <= 10.0):
        raise ValueError("strict scratch only")
    if entrypoint not in ("synthetic","real-worker","hang-fixture"):
        raise ValueError("unsupported scratch entrypoint")
    key=issue_lab_secret()
    fields={"session_id":secrets.token_hex(32),"challenge":secrets.token_hex(32),
            "request_sha256":secrets.token_hex(32),"project_id":project_id,
            "generation":generation}
    wire=json.dumps({"secret":key.hex(),**fields},
                     sort_keys=True,separators=(",",":")).encode("utf-8")+b"\n"
    worker={
        "synthetic":["-m","rag.runtime.knowledge_deletion_mac_child_lab"],
        "real-worker":["-m","rag.runtime.isolated_project_worker","--pinned-mac-scratch"],
        "hang-fixture":["-m","rag.runtime.knowledge_deletion_mac_hang_lab"],
    }[entrypoint]
    proc=subprocess.Popen(
        [sys._base_executable,"-B",*worker],
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
        close_fds=True, shell=False,
    )
    try:
        # Examine the three caller-side pipe ends BEFORE sending the secret.
        # This is evidence of source handle descriptors, not a child ACL audit.
        pipe_evidence=[
            inspect_pipe_fd_acl_dev(stream.fileno())
            for stream in (proc.stdin,proc.stdout,proc.stderr)
        ]
        if not all(
            item["descriptor_observed"] is True
            and item["dacl_present"] is True
            and item["owner_present"] is True
            and item["parent_handle_inheritable"] is False
            for item in pipe_evidence
        ):
            raise RuntimeError("scratch parent pipe security unverified")
        # G-19: deny unexpectedly broad or undecodable ACEs before any secret.
        # This does not attest effective permissions: unknown principal ACEs
        # remain a blocker for the future production authorization process.
        ace_evidence=[
            inspect_pipe_allow_aces_read_only_dev(stream.fileno())
            for stream in (proc.stdin,proc.stdout,proc.stderr)
        ]
        if not all(
            item["state"]=="WIN32_PIPE_ACE_INVENTORY_READ_ONLY"
            and item["dacl_observed"] is True
            and item["broad_allow_ace_detected"] is False
            and item["unsupported_ace_detected"] is False
            and isinstance(item["ace_count"],int)
            and item["ace_count"]>=1
            for item in ace_evidence
        ):
            raise RuntimeError("scratch parent pipe ACE risk unverified")
        try:
            stdout,stderr=proc.communicate(input=wire,timeout=timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            proc.kill()
            proc.communicate()
            raise RuntimeError("scratch child timeout") from exc
        if proc.returncode!=0 or stderr or len(stdout)>1024:
            raise RuntimeError("scratch child blocked")
        response=json.loads(stdout)
        if not isinstance(response,dict) or set(response)!={"pid","mac","birth"}:
            raise RuntimeError("scratch response malformed")
        pid=response["pid"]
        if type(pid) is not int or pid<=0:
            raise RuntimeError("scratch process PID invalid")
        if pid != proc.pid:
            raise RuntimeError("scratch child PID mismatch")
        birth=response["birth"]
        if type(birth) is not int or birth != _creation_filetime(proc._handle):
            raise RuntimeError("scratch Win32 object birth mismatch")
        if not verify_lab_birth_response(key,response["mac"],creation_filetime=birth,
                **fields,child_pid=pid):
            raise RuntimeError("scratch MAC mismatch")
        return {
            "state":"SCRATCH_MAC_PIPE_ROUNDTRIP_ONLY",
            "child_reported_pid":pid,
            "mac_verified":True,
            "spawned_pid_matches_response":True,
            "win32_birth_matches_response":True,
            "parent_pipe_descriptors_observed":True,
            "parent_pipe_ends_not_inheritable":True,
            "parent_pipe_known_broad_aces_absent":True,
            "os_process_identity_attested":False,
            "secure_handle_acl_attested":False,
            "activation_authorized":False,
            "operational_use_allowed":False,
            "read_only":True,
        }
    except (ValueError,TypeError,KeyError) as exc:
        raise RuntimeError("scratch channel invalid") from exc
    finally:
        try:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
        finally:
            # Preflight may reject before communicate() closes pipe streams.
            # Release all parent-side descriptors even on failed ACL evidence.
            for stream in (proc.stdin,proc.stdout,proc.stderr):
                if stream is not None:
                    stream.close()
