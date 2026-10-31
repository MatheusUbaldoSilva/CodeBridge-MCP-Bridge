"""DQ-E-D-3A: strict synthetic semantic request over pinned scratch IPC.

No operational worker or model inference. Request SHA binds a response to the
test request only; it does NOT authenticate a process or prove held locks.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from rag.contracts import SourceType
from rag.runtime.query_classifier import QueryRoute
from rag.runtime.knowledge_deletion_pin_ipc_lab import (
    PrivateReadPinEnvelopeV1, verify_private_pin_envelope_lab,
)


class PinnedSemanticRequestLabError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PinnedSemanticRequestV1:
    schema_version: int
    pin: PrivateReadPinEnvelopeV1
    query: str
    route: str
    top_k: int
    source_types: tuple[str, ...]
    path_filter: str | None
    branch: str | None

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version":self.schema_version,
            "pin":self.pin.to_payload(),
            "query":self.query,
            "route":self.route,
            "top_k":self.top_k,
            "source_types":list(self.source_types),
            "path_filter":self.path_filter,
            "branch":self.branch,
        }

    @classmethod
    def parse(cls, value: Any) -> "PinnedSemanticRequestV1":
        expected={
            "schema_version","pin","query","route","top_k",
            "source_types","path_filter","branch",
        }
        if not isinstance(value,dict) or set(value) != expected:
            raise PinnedSemanticRequestLabError("semantic request schema mismatch")
        if type(value["schema_version"]) is not int or value["schema_version"] != 1:
            raise PinnedSemanticRequestLabError("invalid semantic protocol version")
        pin=PrivateReadPinEnvelopeV1.parse(value["pin"])
        query=value["query"]
        if (not isinstance(query,str) or not 1 <= len(query) <= 4096
                or not query.strip() or "\x00" in query):
            raise PinnedSemanticRequestLabError("invalid semantic query")
        route=value["route"]
        if type(route) is not str or route not in {
            QueryRoute.TEXT.value,QueryRoute.CODE.value,QueryRoute.HYBRID.value,
        }:
            raise PinnedSemanticRequestLabError("semantic route must not be lexical")
        top_k=value["top_k"]
        if type(top_k) is not int or not 1 <= top_k <= 20:
            raise PinnedSemanticRequestLabError("semantic top_k invalid")
        raw_types=value["source_types"]
        allowed={member.value for member in SourceType}
        if (type(raw_types) is not list or len(raw_types)>len(allowed)
                or any(type(item) is not str or item not in allowed
                       for item in raw_types)
                or len(set(raw_types)) != len(raw_types)):
            raise PinnedSemanticRequestLabError("semantic source types invalid")
        for key,limit in (("path_filter",512),("branch",128)):
            item=value[key]
            if item is not None:
                if (not isinstance(item,str) or not item.strip()
                        or len(item)>limit or "\x00" in item):
                    raise PinnedSemanticRequestLabError(f"invalid {key}")
                if key=="path_filter" and (
                    Path(item).is_absolute() or ".." in Path(item).parts
                    or "\\" in item or ":" in item
                ):
                    raise PinnedSemanticRequestLabError("unsafe path filter")
        return cls(
            schema_version=1,pin=pin,query=query,route=route,
            top_k=top_k,source_types=tuple(raw_types),
            path_filter=value["path_filter"],branch=value["branch"],
        )

    def request_digest(self) -> str:
        return sha256(json.dumps(
            self.to_payload(),sort_keys=True,separators=(",",":"),
            ensure_ascii=False,
        ).encode("utf-8")).hexdigest()


def verify_pinned_semantic_request_lab(
    value: PinnedSemanticRequestV1, *, catalog_file: Path,
    laboratory_mode: bool = False,
) -> dict[str, Any]:
    if laboratory_mode is not True:
        raise PermissionError("explicit semantic lab mode required")
    if type(value) is not PinnedSemanticRequestV1:
        raise PinnedSemanticRequestLabError("typed semantic request required")
    request=PinnedSemanticRequestV1.parse(value.to_payload())
    record=verify_private_pin_envelope_lab(
        request.pin,catalog_file=catalog_file,laboratory_mode=True,
    )
    return {
        "state":"LAB_SEMANTIC_REQUEST_VALIDATED",
        "project_id":record["project_id"],
        "generation_id":record["generation_id"],
        "nonce":record["nonce"],
        "request_sha256":request.request_digest(),
        "route":request.route,
        "top_k":request.top_k,
        "result_count":0,
        "model_executed":False,
        "parent_locks_attested_by_worker":False,
        "activation_authorized":False,
        "operational_use_allowed":False,
    }