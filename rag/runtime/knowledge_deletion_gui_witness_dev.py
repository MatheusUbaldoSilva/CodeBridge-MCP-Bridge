"""One-shot DEV GUI loaded-code witness over independent Windows Named Pipe.

Read-only diagnostic: no deletion/queue/catalog writes and NO G32 authorization.
The verifier must check GetNamedPipeServerProcessId and process birth externally.
"""
from __future__ import annotations

import hashlib
import json
import marshal
import os
import re
import sys
import ctypes
from ctypes import wintypes
import threading
import win32api
import win32process

from rag.runtime.knowledge_deletion_scratch_pipe_peer_identity_dev import (
    inspect_scratch_connected_peer_dev,
)


def gui_birth_us():
    return int(
        win32process.GetProcessTimes(
            win32api.GetCurrentProcess()
        )["CreationTime"].timestamp()*1_000_000
    )


def gui_attestation_pipe_name(pid=None, birth=None):
    pid = os.getpid() if pid is None else pid
    birth = gui_birth_us() if birth is None else birth
    if type(pid) is not int or pid <= 0 or type(birth) is not int or birth <= 0:
        raise ValueError("invalid process identity")
    return rf"\\.\pipe\CB.RAGDEL.GUIWITNESS.{pid}.{birth}"


def _code_receipts():
    # Inspect existing in-memory code objects; never compile a fresh file as proof.
    targets = (
        ("rag_panel", "RagPanel", "review_authorization"),
        ("rag_deletion_review_panel", "KnowledgeRemovalReviewPanel", "review_selected"),
    )
    output = {}
    for mod_name, class_name, method in targets:
        module = sys.modules.get(mod_name)
        klass = getattr(module, class_name, None) if module else None
        fun = getattr(klass, method, None)
        if not hasattr(fun, "__code__"):
            output[mod_name + "." + method] = None
            continue
        output[mod_name + "." + method] = {
            "sha256": hashlib.sha256(marshal.dumps(fun.__code__)).hexdigest(),
            "loaded_module_path": getattr(module, "__file__", None),
        }
    return output


def _one_challenge(connection):
    from rag.runtime.knowledge_deletion_scratch_peer_acl_dev import (
        inspect_scratch_connected_peer_effective_access_dev,
    )
    from rag.runtime.knowledge_deletion_scratch_pipe_peer_identity_dev import (
        _client_pid,
    )
    client_pid = wintypes.ULONG()
    if not _client_pid(connection._handle, ctypes.byref(client_pid)):
        raise RuntimeError("kernel client identity missing")
    peer_access = inspect_scratch_connected_peer_effective_access_dev(
        connection, expected_client_pid=client_pid.value,
    )
    if (peer_access["state"] != "SCRATCH_PEER_KERNEL_TOKEN_ACCESSCHECK_COMPLETE"
        or peer_access["access_granted"] is not True):
        raise PermissionError("peer kernel DACL AccessCheck rejected")
    raw = connection.receive()
    if len(raw) > 256:
        raise ValueError("oversized witness challenge")
    challenge = raw.decode("ascii")
    if re.fullmatch(r"[0-9a-f]{64}", challenge) is None:
        raise ValueError("malformed witness challenge")
    reply = {
        "schema": "RAG_DEL_GUI_WITNESS_DEV_V1",
        "challenge": challenge,
        "pid": os.getpid(),
        "birth_us": gui_birth_us(),
        "code_receipts": _code_receipts(),
        "observed_peer_pid": client_pid.value,
        "peer_effective_read_access": peer_access["access_granted"],
        "peer_accesscheck_completed": peer_access["access_check_completed"],
        "installed_gui_attested_for_operational_deletion": False,
        "activation_authorized": False,
        "operational_use_allowed": False,
    }
    connection.send(json.dumps(reply, sort_keys=True).encode("utf-8"))
    # Keep pipe open for client to read before disconnect (WinError 233).
    if connection.receive() != b"CLOSE":
        raise ValueError("invalid witness close handshake")
    return reply


def start_dev_gui_witness():
    """Non-blocking; only starts a single diagnostic connection on DEV GUI."""
    import ipc_named_pipe
    name = gui_attestation_pipe_name()
    def serve():
        try:
            with ipc_named_pipe.NamedPipeServer(name).accept() as connection:
                _one_challenge(connection)
        except Exception:
            # Diagnostic never alters normal GUI startup/availability.
            return
    worker = threading.Thread(
        target=serve, name="RAGDEL-GUI-witness-DEV", daemon=True
    )
    worker.start()
    return name
