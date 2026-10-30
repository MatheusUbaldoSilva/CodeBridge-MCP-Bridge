"""RAG-DEL-01.03-C: immutable candidate evidence receipt; never activates."""
from __future__ import annotations
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import tempfile

from rag.runtime.auto_index_incremental_plan import IncrementalPlanError

SHA = re.compile(r"[0-9a-f]{64}\Z")
ARTIFACTS = ("rag_index.sqlite3", "rag-index-manifest.json")


def _digest(path: Path) -> str:
    h = sha256()
    with path.open("rb") as source:
        for part in iter(lambda: source.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def _canonical(stage: Path, filename: str) -> Path:
    path = stage / filename
    if (path.is_symlink() or not path.is_file()
            or path.resolve(strict=True).parent != stage.resolve(strict=True)):
        raise IncrementalPlanError("candidate artifact missing or redirected")
    return path


def seal_deletion_candidate(stage_path: str | Path, preview: dict, verification: dict,
                             *, operator_approved: bool = False) -> dict:
    """Write one immutable evidence receipt only in a supplied stage directory."""
    if operator_approved is not True:
        raise PermissionError("explicit isolated receipt approval required")
    stage = Path(stage_path)
    if not stage.is_dir() or stage.is_symlink() or (
        hasattr(stage, "is_junction") and stage.is_junction()
    ):
        raise IncrementalPlanError("unsafe candidate stage")
    if (not isinstance(preview, dict)
            or preview.get("mode") != "READ_ONLY_REMOVAL_PREVIEW"
            or preview.get("deletion_authorized") is not False
            or not isinstance(preview.get("review_sha256"), str)
            or not SHA.fullmatch(preview["review_sha256"])
            or not isinstance(preview.get("selected_paths"), list)
            or not preview["selected_paths"]):
        raise IncrementalPlanError("invalid pinned removal preview")
    if (not isinstance(verification, dict)
            or verification.get("state") != "DELETION_STAGING_STRUCTURALLY_VALID"
            or verification.get("activation_authorized") is not False
            or verification.get("project_id") != preview.get("project_id")
            or verification.get("documents") != preview.get("documents_to_preserve")
            or verification.get("chunks") != preview.get("chunks_to_preserve")
            or verification.get("vectors_verified") != preview.get("chunks_to_preserve")):
        raise IncrementalPlanError("unverified candidate or mismatched inventory")
    hashes = {filename: _digest(_canonical(stage, filename)) for filename in ARTIFACTS}
    data = {
        "schema_version": 1, "state": "EVIDENCE_ONLY_NOT_ACTIVATABLE",
        "project_id": preview["project_id"],
        "baseline_generation": preview.get("generation"),
        "baseline_revision": preview.get("source_revision"),
        "selection_sha256": preview["review_sha256"],
        "selected_paths": sorted(preview["selected_paths"]),
        "documents": verification["documents"], "chunks": verification["chunks"],
        "vectors_verified": verification["vectors_verified"],
        "artifact_sha256": hashes,
        "public_pointer_updated": False,
        "activation_authorized": False,
    }
    serialized = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    data["receipt_sha256"] = sha256(serialized).hexdigest()
    target = stage / "deletion-candidate-evidence.json"
    temp = stage / "deletion-candidate-evidence.writing"
    if target.exists() or temp.exists() or target.is_symlink() or temp.is_symlink():
        raise IncrementalPlanError("receipt exists or interrupted write requires review")
    fd = None
    try:
        fd = os.open(temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "wb") as stream:
            fd = None
            stream.write(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8") + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, target)
    finally:
        if fd is not None:
            os.close(fd)
    return {"state": data["state"], "receipt": str(target),
            "receipt_sha256": data["receipt_sha256"], "activation_authorized": False}


def inspect_deletion_candidate_evidence(stage_path: str | Path) -> dict:
    stage = Path(stage_path)
    receipt = _canonical(stage, "deletion-candidate-evidence.json")
    if receipt.stat().st_size > 1024 * 1024:
        raise IncrementalPlanError("candidate receipt unexpectedly large")
    data = json.loads(receipt.read_text(encoding="utf-8"))
    digest = data.pop("receipt_sha256", None)
    raw = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    if (not isinstance(digest, str) or digest != sha256(raw).hexdigest()
            or data.get("state") != "EVIDENCE_ONLY_NOT_ACTIVATABLE"
            or data.get("activation_authorized") is not False
            or data.get("public_pointer_updated") is not False
            or not isinstance(data.get("artifact_sha256"), dict)
            or set(data["artifact_sha256"]) != set(ARTIFACTS)):
        raise IncrementalPlanError("candidate receipt failed integrity")
    for name in ARTIFACTS:
        if _digest(_canonical(stage, name)) != data["artifact_sha256"][name]:
            raise IncrementalPlanError("candidate artifact changed after sealing")
    return {**data, "receipt_sha256": digest}
