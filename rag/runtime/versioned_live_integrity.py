"""Read-only cross-store verifier for the pinned production CodeBridge generation.

Requires its caller to hold production_generation_read() shared lock.
Uses standard-library SQLite and UUID opcode inspection; does NOT require
the optional qdrant-client package used by offline batch validators.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from rag.runtime.live_integrity import LiveIntegrityError, _inspect_storage_root
from rag.runtime.status import resolve_rag_state_directory

_GENERATION = re.compile(r"^v1_(base|delta)_[0-9a-f]{14}$")
_FILES = (
    "rag_index.sqlite3",
    "rag-index-manifest.json",
    "qdrant/meta.json",
    "qdrant/collection/text/storage.sqlite",
    "qdrant/collection/code/storage.sqlite",
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inspect_pinned_index(pinned) -> dict:
    """Verify the already-pinned generation without changing the active pointer."""
    state = resolve_rag_state_directory().resolve()
    if pinned.generation == "legacy":
        legacy = state
        if not (pinned.sqlite.resolve() == legacy / "rag_index.sqlite3"
                and pinned.manifest.resolve() == legacy / "rag-index-manifest.json"
                and pinned.qdrant.resolve() == legacy / "qdrant"):
            raise LiveIntegrityError("legacy pointer storage mismatch")
        result = _inspect_storage_root(legacy)
        result["audited_generation"] = "legacy"
        result["receipt_hashes_verified"] = False
        return result

    match = _GENERATION.fullmatch(pinned.generation)
    if match is None:
        raise LiveIntegrityError("unsupported production generation name")
    root = (state / "generations").resolve()
    target = (root / pinned.generation).resolve(strict=True)
    if target.parent != root or not target.is_dir():
        raise LiveIntegrityError("generation outside approved storage")
    if (pinned.sqlite.resolve() != target / "rag_index.sqlite3"
            or pinned.manifest.resolve() != target / "rag-index-manifest.json"
            or pinned.qdrant.resolve() != target / "qdrant"):
        raise LiveIntegrityError("pinned generation paths mismatch")
    receipt_file = target / "generation-receipt.json"
    receipt = json.loads(receipt_file.read_text(encoding="utf-8"))
    if (receipt.get("generation") != pinned.generation
            or receipt.get("label") != match.group(1)
            or receipt.get("status") != "VERSIONED_GENERATION_VALIDATED_NOT_ACTIVE"
            or receipt.get("activation_permitted") is not False
            or receipt.get("active_pointer_updated") is not False
            or Path(receipt.get("directory", "")).resolve() != target):
        raise LiveIntegrityError("generation provenance receipt mismatch")
    expected_hashes = receipt.get("file_sha256")
    if not isinstance(expected_hashes, dict) or set(expected_hashes) != set(_FILES):
        raise LiveIntegrityError("generation hash manifest missing or incomplete")
    for relative in _FILES:
        stored = (target / relative).resolve(strict=True)
        if not stored.is_relative_to(target) or not stored.is_file():
            raise LiveIntegrityError("generation file escapes approved root: " + relative)
        if _sha256_file(stored) != expected_hashes[relative]:
            raise LiveIntegrityError("generation data hash changed: " + relative)

    result = _inspect_storage_root(target)
    recorded = receipt.get("validation") or {}
    if (result["documents"] != recorded.get("documents")
            or result["chunks"] != recorded.get("chunks")
            or result["manifest_entries"] != recorded.get("manifest_entries")
            or sum(v["vectors"] for v in result["collections"].values()) != recorded.get("vectors")):
        raise LiveIntegrityError("live vector identity counts differ from generation receipt")
    for relative in _FILES:
        if _sha256_file(target / relative) != expected_hashes[relative]:
            raise LiveIntegrityError("generation data changed during read: " + relative)
    result["audited_generation"] = pinned.generation
    result["receipt_hashes_verified"] = True
    result["note"] = (
        "Read-only versioned generation content and receipt audit; "
        "does not authorize activation or mark GO-LIVE"
    )
    return result
