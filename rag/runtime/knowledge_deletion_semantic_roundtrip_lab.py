"""DQ-E-D-3B: scratch-only parent-side response correlation / timeout.

Not an authenticated IPC channel. Never authorizes semantic model execution,
knowledge deletion, installed service activation, or a production cutover.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable

from rag.runtime.knowledge_deletion_semantic_dispatch_lab import (
    dispatch_semantic_already_locked_lab,
)
from rag.runtime.knowledge_deletion_semantic_request_lab import (
    PinnedSemanticRequestV1,
)
from rag.runtime.knowledge_deletion_private_read_session_lab import PrivateLabPin


class SemanticRoundtripLabError(RuntimeError):
    pass


_RESPONSE_KEYS=frozenset({
    "state","project_id","generation_id","nonce","request_sha256",
    "route","top_k","result_count","model_executed",
    "parent_locks_attested_by_worker","activation_authorized",
    "operational_use_allowed",
})


def execute_semantic_roundtrip_lab(
    query: Any, route: Any, *, pin: PrivateLabPin, catalog_file: Path,
    timeout_seconds: float = 5.0, runner: Callable[..., Any] = subprocess.run,
    laboratory_mode: bool = False, operator_approved: bool = False,
) -> dict[str, Any]:
    """Invoke real synthetic child while parent retains all private locks."""
    if laboratory_mode is not True or operator_approved is not True:
        raise PermissionError("scratch semantic roundtrip requires lab approval")
    if (type(timeout_seconds) not in (int,float)
            or not 0 < timeout_seconds <= 10
            or timeout_seconds != timeout_seconds
            or timeout_seconds == float("inf")):
        raise ValueError("bounded child timeout must be 0..10 seconds")
    if not callable(runner):
        raise TypeError("subprocess runner required")

    def _dispatch(q,r,envelope):
        request=PinnedSemanticRequestV1.parse({
            "schema_version":1,"pin":envelope.to_payload(),
            "query":q.query,"route":r.value,"top_k":q.top_k,
            "source_types":[item.value for item in q.source_types],
            "path_filter":q.path_filter,"branch":q.branch,
        })
        root=Path(catalog_file).absolute().parent
        try:
            complete=runner(
                [sys.executable,"-m",
                 "rag.runtime.knowledge_deletion_pin_worker_lab",
                 str(root),"--semantic-request"],
                cwd=str(Path(__file__).resolve().parents[2]),
                input=json.dumps(request.to_payload()),text=True,
                capture_output=True,check=False,timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise SemanticRoundtripLabError("scratch semantic child timed out") from exc
        if complete.returncode != 0:
            raise SemanticRoundtripLabError("scratch semantic child failed closed")
        try:
            response=json.loads(complete.stdout)
        except (ValueError,TypeError) as exc:
            raise SemanticRoundtripLabError("scratch semantic response invalid JSON") from exc
        if not isinstance(response,dict) or set(response) != _RESPONSE_KEYS:
            raise SemanticRoundtripLabError("scratch semantic response schema mismatch")
        for key,expected in (
            ("state","LAB_SEMANTIC_REQUEST_VALIDATED"),
            ("project_id",request.pin.project_id),
            ("generation_id",request.pin.generation_id),
            ("nonce",request.pin.nonce),
            ("request_sha256",request.request_digest()),
            ("route",request.route),("top_k",request.top_k),
        ):
            if type(response[key]) is not type(expected) or response[key] != expected:
                raise SemanticRoundtripLabError(f"scratch semantic response {key} mismatch")
        if (type(response["result_count"]) is not int
                or response["result_count"] != 0
                or response["model_executed"] is not False
                or response["parent_locks_attested_by_worker"] is not False
                or response["activation_authorized"] is not False
                or response["operational_use_allowed"] is not False):
            raise SemanticRoundtripLabError("synthetic worker crossed operational gate")
        return {
            "state":"LAB_PINNED_SEMANTIC_ROUNDTRIP_ONLY",
            "project_id":request.pin.project_id,
            "generation_id":request.pin.generation_id,
            "request_sha256":request.request_digest(),
            "nonce":request.pin.nonce,
            "result_count":0,
            "model_executed":False,
            "activation_authorized":False,
            "operational_use_allowed":False,
        }

    return dispatch_semantic_already_locked_lab(
        query,route,pin=pin,catalog_file=catalog_file,
        executor=_dispatch,laboratory_mode=True,operator_approved=True,
    )