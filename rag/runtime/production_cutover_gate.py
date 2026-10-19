"""Read-only readiness gate for CodeBridge RAG V1 generation cutover.

Verifies both immutable generation candidates, legacy integrity and source
provenance. This module never creates a pointer, approves activation or writes
to active SQLite / Qdrant. It intentionally fails closed pending MCP reload
and atomic recovery protocol completion.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from rag.runtime.status import resolve_rag_sqlite_path
from rag.runtime.live_integrity import inspect_live_index


_PROTECTED = (
    "rag_index.sqlite3", "rag-index-manifest.json", "qdrant/meta.json",
    "qdrant/collection/text/storage.sqlite",
    "qdrant/collection/code/storage.sqlite",
)


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _verify_versioned(root: Path, name: str, label: str) -> dict:
    if not name.startswith("v1_" + label + "_"):
        raise ValueError("unexpected versioned generation identifier")
    parent = (root / "generations").resolve()
    directory = (parent / name).resolve(strict=True)
    if not directory.is_relative_to(parent) or not directory.is_dir():
        raise ValueError("generation root outside CodeBridge versioned storage")
    file = directory / "generation-receipt.json"
    data = json.loads(file.read_text(encoding="utf-8"))
    if (data.get("status") != "VERSIONED_GENERATION_VALIDATED_NOT_ACTIVE"
            or data.get("generation") != name
            or data.get("label") != label
            or data.get("activation_permitted") is not False):
        raise ValueError("generation identity or no-activation receipt invalid")
    for relative in _PROTECTED:
        if _sha(directory / relative) != data["file_sha256"][relative]:
            raise ValueError("versioned bundle hash drift: " + relative)
    # Some packaged MCP runtimes do not ship the offline Qdrant validator.
    # Absence must block the cutover, never weaken validation.
    from rag.runtime.incremental_bundle_validate import validate_incremental_bundle
    validated = validate_incremental_bundle(directory)
    if validated != data["validation"]:
        raise ValueError("versioned bundle changed since receipt")
    return {"generation": name, "validation": validated, "sha_verified": True}


def assess_real_cutover(baseline: str, candidate: str) -> dict:
    state = resolve_rag_sqlite_path().resolve().parent
    if state.name != "rag" or state.parent.name != "CodeBridge":
        raise ValueError("not a real CodeBridge RAG installation")
    blockers = [
        "PUBLIC_MCP_READERS_RESTART_NOT_ATTESTED",
        "ATOMIC_PRODUCTION_POINTER_WRITER_AND_ROLLBACK_NOT_VALIDATED",
    ]
    reasons = []
    checked = {}
    try:
        base = _verify_versioned(state, baseline, "base")
        updated = _verify_versioned(state, candidate, "delta")
        checked["baseline"] = base
        checked["candidate"] = updated
        before = base["validation"]
        after = updated["validation"]
        if after["documents"] != before["documents"] + 1 or (
            after["vectors"] != before["vectors"] + 5
        ):
            reasons.append("UNEXPECTED_GENERATION_DELTA")
        active = inspect_live_index()
        checked["legacy"] = {
            "documents": active["documents"], "chunks": active["chunks"],
        }
        if (active["documents"] != before["documents"]
                or active["chunks"] != before["chunks"]):
            reasons.append("LEGACY_INDEX_DRIFT")
    except (OSError, ValueError, KeyError, RuntimeError, ImportError) as exc:
        reasons.append("INTEGRITY_PROOF_FAILED: " + str(exc))
    if (state / "production-generation-transition.json").exists():
        reasons.append("RECOVERY_JOURNAL_PENDING")
    if (state / "active-generation.json").exists():
        reasons.append("ACTIVE_POINTER_ALREADY_EXISTS")
    return {
        "state": "BLOCKED" if blockers or reasons else "READY",
        "safe_to_activate": False,
        "read_only": True,
        "blockers": blockers + reasons,
        "verified": checked,
        "recovery_preserved": True,
        "pointer_updated": False,
    }
