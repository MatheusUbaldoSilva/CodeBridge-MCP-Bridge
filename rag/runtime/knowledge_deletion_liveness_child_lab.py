"""DQ-E-D-3C-E-2: TEMP-only child that requires a living parent pipe.

This is a synthetic watchdog, never a model or production worker.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
from threading import Thread
import time

from rag.runtime.knowledge_deletion_bounded_catalog_lab import _validated_scratch_catalog
from rag.runtime.knowledge_deletion_semantic_request_lab import (
    PinnedSemanticRequestV1, verify_pinned_semantic_request_lab,
)
from rag.runtime.knowledge_deletion_vector_tree_receipt_lab import (
    create_vector_tree_receipt_lab,
)


def _mark_failure(root: Path, state: str) -> None:
    # Only TEMP test evidence. Never writes to a model, catalog, or index.
    # Exclusive creation prevents overwriting a pre-existing path or link.
    with (root / "lab-child-termination.json").open("x",encoding="utf-8") as out:
        json.dump({"state":state},out)


_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_STILL_ACTIVE = 259
_kernel32 = ctypes.WinDLL("kernel32",use_last_error=True)
_open_process = _kernel32.OpenProcess
_open_process.argtypes = [wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
_open_process.restype = wintypes.HANDLE
_get_exit_code = _kernel32.GetExitCodeProcess
_get_exit_code.argtypes = [wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)]
_get_exit_code.restype = wintypes.BOOL
_close_handle = _kernel32.CloseHandle
_close_handle.argtypes = [wintypes.HANDLE]
_close_handle.restype = wintypes.BOOL


def _held_parent_handle_still_active(handle: wintypes.HANDLE) -> bool:
    # A persistent Win32 handle refers to ONE process object: PID reuse
    # cannot cause this check to switch to an unrelated process.
    code=wintypes.DWORD(0)
    return bool(_get_exit_code(handle,ctypes.byref(code))) and code.value == _STILL_ACTIVE


def _read_ack_bounded(parent_handle: wintypes.HANDLE, seconds: float = 8.0) -> str | None:
    lines: list[str] = []
    def read():
        lines.append(sys.stdin.readline(130))
    thread=Thread(target=read,daemon=True)
    thread.start()
    deadline=time.monotonic()+seconds
    while True:
        # PID liveness is independent of EOF delivery; polling stops a child
        # promptly even when Windows delays closing an inherited pipe.
        if not _held_parent_handle_still_active(parent_handle):
            return "__PARENT_PROCESS_EXITED__"
        remaining=deadline-time.monotonic()
        if remaining<=0:
            return None
        thread.join(min(0.05,remaining))
        if not thread.is_alive():
            return lines[0] if lines else ""


def _parse_one_shot_scratch_ack_lab(ack: str, nonce: str) -> str:
    """Return digest of fresh parent challenge, not the challenge itself.

    This is a *scratch only* anti-stale-response correlation check.
    The parent is NOT cryptographically authenticated by this protocol.
    """
    prefix="ACK "+nonce+" "
    if (not isinstance(ack,str) or not ack.startswith(prefix)
            or not ack.endswith("\n")
            or len(ack)!=len(prefix)+64+1):
        raise ValueError("scratch ACK challenge schema mismatch")
    challenge=ack[len(prefix):-1]
    if any(character not in "0123456789abcdef" for character in challenge):
        raise ValueError("scratch ACK challenge is not lowercase hexadecimal")
    return sha256(bytes.fromhex(challenge)).hexdigest()


def main() -> None:
    if len(sys.argv)!=3:
        raise PermissionError("scratch child requires lab root and parent PID")
    return run_supervised_scratch_child_lab(sys.argv[1],sys.argv[2])


def run_supervised_scratch_child_lab(root_arg: str, parent_pid_arg: str) -> None:
    """Entry for the isolated worker's strictly scratch-only opt-in mode."""
    if (not isinstance(parent_pid_arg,str) or not parent_pid_arg.isdigit()
            or not 1 <= int(parent_pid_arg) < 0xFFFFFFFF):
        raise PermissionError("scratch child requires valid parent PID")
    parent_pid=int(parent_pid_arg)
    if parent_pid == os.getpid():
        raise PermissionError("parent must not be the child process")
    parent_handle=_open_process(_PROCESS_QUERY_LIMITED_INFORMATION,False,parent_pid)
    if not parent_handle:
        raise PermissionError("scratch parent process cannot be pinned")
    try:
        if not _held_parent_handle_still_active(parent_handle):
            raise PermissionError("scratch parent process already exited")
        _run_pinned_child_with_parent_handle(Path(root_arg),parent_handle)
    finally:
        _close_handle(parent_handle)


def _run_pinned_child_with_parent_handle(root: Path, parent_handle: wintypes.HANDLE) -> None:
    catalog, root=_validated_scratch_catalog(root/"project-indexes.json")
    raw=sys.stdin.readline(8193)
    if len(raw)>8192:
        raise ValueError("oversized liveness request")
    message=json.loads(raw)
    if not isinstance(message,dict) or set(message)!={"request","tree_sha256"}:
        raise ValueError("scratch liveness IPC schema mismatch")
    request=PinnedSemanticRequestV1.parse(message["request"])
    digest=message["tree_sha256"]
    if not isinstance(digest,str) or len(digest)!=64:
        raise ValueError("invalid vector tree fingerprint")
    verify_pinned_semantic_request_lab(
        request,catalog_file=catalog,laboratory_mode=True,
    )
    observed=create_vector_tree_receipt_lab(
        request.pin,catalog_file=catalog,laboratory_mode=True,
    )
    if not observed.files or observed.tree_sha256!=digest:
        raise RuntimeError("scratch vector receipt mismatch")
    print("CHILD_VERIFIED",flush=True)
    ack=_read_ack_bounded(parent_handle)
    if ack=="__PARENT_PROCESS_EXITED__":
        _mark_failure(root,"PARENT_PROCESS_EXITED")
        raise SystemExit(72)
    if ack is None:
        _mark_failure(root,"CHILD_ACK_TIMEOUT")
        raise SystemExit(74)
    if ack=="":
        _mark_failure(root,"PARENT_PIPE_CLOSED")
        raise SystemExit(72)
    try:
        challenge_digest=_parse_one_shot_scratch_ack_lab(
            ack,request.pin.nonce,
        )
    except ValueError:
        _mark_failure(root,"CHILD_ACK_REJECTED")
        raise SystemExit(73)
    if not _held_parent_handle_still_active(parent_handle):
        _mark_failure(root,"PARENT_PROCESS_EXITED")
        raise SystemExit(72)
    verify_pinned_semantic_request_lab(
        request,catalog_file=catalog,laboratory_mode=True,
    )
    after=create_vector_tree_receipt_lab(
        request.pin,catalog_file=catalog,laboratory_mode=True,
    )
    if after != observed:
        _mark_failure(root,"CHILD_VECTOR_DRIFT")
        raise SystemExit(75)
    if not _held_parent_handle_still_active(parent_handle):
        _mark_failure(root,"PARENT_PROCESS_EXITED")
        raise SystemExit(72)
    print(json.dumps({
        "state":"LAB_CHILD_COMPLETED_WHILE_PARENT_PIPE_OPEN",
        "project_id":request.pin.project_id,
        "generation_id":request.pin.generation_id,
        "nonce":request.pin.nonce,
        "request_sha256":request.request_digest(),
        "tree_sha256":digest,
        "challenge_sha256":challenge_digest,
        "operational_use_allowed":False,
        "activation_authorized":False,
    },sort_keys=True),flush=True)


if __name__=="__main__":
    main()