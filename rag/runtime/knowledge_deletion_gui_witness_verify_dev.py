"""Read-only external kernel-pinned verifier of the DEV GUI witness.

Never authorizes RAG deletion; witnesses are not proof of per-request authorization.
"""
from __future__ import annotations
import ctypes
from ctypes import wintypes
import hashlib
import json
import secrets
import marshal
import os

import win32api
import win32con
import win32process
import win32security

from rag.runtime.knowledge_deletion_gui_witness_dev import gui_attestation_pipe_name

_kernel = ctypes.WinDLL("kernel32", use_last_error=True)
_get_server_pid = _kernel.GetNamedPipeServerProcessId
_get_server_pid.argtypes = [wintypes.HANDLE,ctypes.POINTER(wintypes.ULONG)]
_get_server_pid.restype = wintypes.BOOL


def verify_dev_gui_witness(*, expected_pid: int, expected_birth_us: int, timeout=4):
    """Connect once to exact pinned process identity; reject server-PID spoof."""
    if type(expected_pid) is not int or expected_pid <= 0 or (
        type(expected_birth_us) is not int or expected_birth_us <= 0
    ):
        raise ValueError("pinned DEV GUI process identity required")
    result = dict(
        state="GUI_WITNESS_UNVERIFIED", read_only=True,
        expected_pid=expected_pid, expected_birth_us=expected_birth_us,
        observed_server_pid=None, challenge_bound=False,
        loaded_code_receipts={}, blockers=[],
        expected_loaded_code_matches=False, peer_accesscheck_observed=False,
        installed_gui_loaded_code_observed=False,
        installed_gui_operationally_attested=False,
        ipc_peer_effective_acl_attested=False,
        activation_authorized=False, operational_use_allowed=False,
    )
    # Import via selected GUI path and reject unexpected transport.
    import sys
    from pathlib import Path
    app_root = str(Path(__file__).resolve().parents[2]/"app_rewrite")
    if app_root not in sys.path:
        sys.path.insert(0,app_root)
    from ipc_named_pipe import NamedPipeClient
    try:
        process = win32api.OpenProcess(
            win32con.PROCESS_QUERY_LIMITED_INFORMATION,False,expected_pid
        )
        try:
            observed_birth = int(
                win32process.GetProcessTimes(process)["CreationTime"].timestamp()*1_000_000
            )
        finally:
            process.Close()
        if observed_birth != expected_birth_us:
            result["blockers"].append("EXPECTED_PROCESS_BIRTH_CHANGED")
            return result
        with NamedPipeClient.connect(
            gui_attestation_pipe_name(expected_pid,expected_birth_us),
            timeout=timeout
        ) as conn:
            server_pid = wintypes.ULONG()
            if not _get_server_pid(conn._handle,ctypes.byref(server_pid)):
                result["blockers"].append("KERNEL_SERVER_PID_UNVERIFIED")
                return result
            result["observed_server_pid"] = server_pid.value
            if server_pid.value != expected_pid:
                result["blockers"].append("KERNEL_SERVER_PID_MISMATCH")
                return result
            challenge = secrets.token_hex(32)
            conn.send(challenge.encode("ascii"))
            response = conn.receive()
            conn.send(b"CLOSE")
        if len(response) > 8192:
            result["blockers"].append("OVERSIZED_WITNESS")
            return result
        report = json.loads(response.decode("utf-8"))
        if (type(report) is not dict
            or report.get("schema") != "RAG_DEL_GUI_WITNESS_DEV_V1"
            or report.get("pid") != expected_pid
            or report.get("birth_us") != expected_birth_us
            or report.get("challenge") != challenge
            or report.get("observed_peer_pid") != os.getpid()
            or report.get("peer_effective_read_access") is not True
            or report.get("peer_accesscheck_completed") is not True
            or report.get("activation_authorized") is not False
            or report.get("operational_use_allowed") is not False
            or report.get("installed_gui_attested_for_operational_deletion") is not False):
            result["blockers"].append("WITNESS_RESPONSE_INVALID")
            return result
        result["challenge_bound"] = True
        receipts = report.get("code_receipts")
        if type(receipts) is not dict or not receipts or any(
            type(rec) is not dict
            or type(rec.get("sha256")) is not str
            or len(rec["sha256"]) != 64
            or type(rec.get("loaded_module_path")) is not str
            for rec in receipts.values()
        ):
            result["blockers"].append("LOADED_CODE_RECEIPTS_MISSING")
            return result
        result["peer_accesscheck_observed"] = True
        from rag_panel import RagPanel
        from rag_deletion_review_panel import KnowledgeRemovalReviewPanel
        expected = {
            "rag_panel.review_authorization": (
                RagPanel.review_authorization, Path(app_root)/"rag_panel.py"
            ),
            "rag_deletion_review_panel.review_selected": (
                KnowledgeRemovalReviewPanel.review_selected,
                Path(app_root)/"rag_deletion_review_panel.py"
            ),
        }
        if set(receipts) != set(expected) or any(
            receipts[key]["sha256"] != hashlib.sha256(
                marshal.dumps(expected[key][0].__code__)
            ).hexdigest()
            or Path(receipts[key]["loaded_module_path"]).resolve() != expected[key][1].resolve()
            for key in expected
        ):
            result["blockers"].append("INSTALLED_GUI_LOADED_CODE_MISMATCH")
            return result
        result["expected_loaded_code_matches"] = True
        result["loaded_code_receipts"] = receipts
        result["installed_gui_loaded_code_observed"] = True
        result["state"] = "GUI_LOADED_CODE_KERNEL_PINNED_READONLY"
    except (OSError,ValueError,TypeError,UnicodeError,KeyError,json.JSONDecodeError):
        result["blockers"].append("GUI_WITNESS_CONNECTION_OR_PROCESS_UNVERIFIED")
    return result
