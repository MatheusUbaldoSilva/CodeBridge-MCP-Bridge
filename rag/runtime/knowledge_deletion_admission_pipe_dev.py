"""DEV-only one-shot Named Pipe precheck service, absolutely no deletion action.

Uses the actual source NamedPipeServer and Windows connected client process
token AccessCheck. The only opcode is PRECHECK and the result always carries
activation_authorized=False. Intended for an isolated scratch process.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import re
import secrets
import hmac
from pathlib import Path
import sys

from rag.runtime.knowledge_deletion_scratch_pipe_peer_identity_dev import _client_pid
from rag.runtime.knowledge_deletion_scratch_peer_acl_dev import (
    inspect_scratch_connected_peer_effective_access_dev,
)
from rag.runtime.knowledge_deletion_operational_admission_dev import (
    review_operational_deletion_admission,
)

_APP = str(Path(__file__).resolve().parents[2]/"app_rewrite")
if _APP not in sys.path:
    sys.path.insert(0,_APP)
from ipc_named_pipe import NamedPipeServer

MAX_MESSAGE_BYTES = 8192
_PIPE_PREFIX = r'\\.\pipe\CB.RAGDEL.ADMISSION.SCRATCH.'
_PIPE_LEAF = re.compile(r'[0-9a-f]{32}\Z')

def serve_one_deletion_admission_precheck_dev(
    pipe_name: str, *, get_gui_witness, get_operational_inventory,
    get_project_conflicts=None, get_server_review=None,
    now_epoch: int | None = None,
) -> dict:
    """One-shot scratch IPC handler. NOT installed in actual GUI."""
    if (not isinstance(pipe_name,str) or not pipe_name.startswith(_PIPE_PREFIX)
            or _PIPE_LEAF.fullmatch(pipe_name[len(_PIPE_PREFIX):]) is None):
        raise ValueError("only randomized disposable admission pipes are permitted")
    if not callable(get_gui_witness) or not callable(get_operational_inventory):
        raise TypeError("trusted read-only server observers required")
    with NamedPipeServer(pipe_name).accept() as connection:
        client_pid=wintypes.ULONG()
        if not _client_pid(connection._handle,ctypes.byref(client_pid)):
            raise RuntimeError("unverifiable IPC kernel client")
        peer=inspect_scratch_connected_peer_effective_access_dev(
            connection, expected_client_pid=client_pid.value, desired_access=1
        )
        if peer["state"]!="SCRATCH_PEER_KERNEL_TOKEN_ACCESSCHECK_COMPLETE" or peer["access_granted"] is not True:
            raise PermissionError("untrusted kernel connected peer")
        # Native kernel token check is complete before issuing a challenge.
        # A freshly generated one-time challenge binds this request to the
        # current connection. Replayed client payloads are never accepted.
        challenge=secrets.token_hex(32)
        connection.send(json.dumps({
            "schema":"RAG_DEL_ADMISSION_PRECHECK_CHALLENGE_V1",
            "challenge":challenge,
            "read_only":True,
        },sort_keys=True).encode("utf-8"))
        raw=connection.receive()
        if len(raw)>MAX_MESSAGE_BYTES:
            raise ValueError("oversized request")
        try:
            message=json.loads(raw.decode("utf-8"))
        except (UnicodeError,ValueError) as exc:
            raise ValueError("invalid precheck request") from exc
        if (type(message) is not dict
                or type(message.get("challenge")) is not str
                or not hmac.compare_digest(message["challenge"],challenge)):
            raise ValueError("stale or mismatched admission challenge")
        if (set(message)!={"schema","challenge","operation","request"}
                or message.get("schema")!="RAG_DEL_ADMISSION_PRECHECK_REQUEST_V1"
                or message["operation"]!="PRECHECK"):
            result=dict(state="RAG_DEL_COMMAND_ADMISSION_BLOCKED",blockers=["UNSUPPORTED_OPERATION"],
                        read_only=True,activation_authorized=False,
                        deletion_enabled=False,operational_use_allowed=False)
        else:
            # The peer does not provide its own GUI or queue receipts.
            request=message["request"]
            scoped=None
            if get_project_conflicts is not None and type(request) is dict:
                # Independent server-side observer; never from JSON payload.
                if not callable(get_project_conflicts):
                    raise TypeError("invalid project conflict observer")
                scoped=get_project_conflicts(request.get("project_id"))
            source_review=None
            if get_server_review is not None:
                if not callable(get_server_review):
                    raise TypeError("invalid server-side read-only review")
                try:
                    source_review=get_server_review(
                        request.get("project_id"),request.get("selected_paths")
                    )
                except (ValueError,OSError,RuntimeError,TypeError):
                    source_review={"state":"SERVER_REVIEW_UNAVAILABLE"}
            result=review_operational_deletion_admission(
                request,gui_witness=get_gui_witness(),
                operational_inventory=get_operational_inventory(),
                target_conflicts=scoped,server_review=source_review,
                now_epoch=now_epoch
            )
        result["kernel_connected_client_pid"]=client_pid.value
        result["kernel_peer_accesscheck_complete"]=peer["access_check_completed"]
        result["activation_authorized"]=False
        result["operational_use_allowed"]=False
        result["deletion_enabled"]=False
        connection.send(json.dumps(result,sort_keys=True).encode("utf-8"))
        if connection.receive()!=b"CLOSE":
            raise ValueError("bad client close handshake")
        return result
