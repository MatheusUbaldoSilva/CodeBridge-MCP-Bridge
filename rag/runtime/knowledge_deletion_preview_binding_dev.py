"""F16 DEV-only consistency review: explicit selection vs read-only RAG preview.

No live preview call, filesystem/queue/index read, process attestation,
trusted signature, deletion or mutation. All operational gates remain FALSE.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re

from rag.runtime.knowledge_deletion_selection_contract_dev import (
    review_explicit_deletion_paths_dev,
)

_SOURCE_FIELDS = frozenset((
    "schema_version", "mode", "project_id", "generation",
    "source_revision", "selected_paths", "documents_to_remove",
    "chunks_to_remove", "documents_to_preserve", "chunks_to_preserve",
))
_COMPLETION_FLAGS = frozenset((
    "operator_approved", "deletion_authorized", "candidate_created",
    "public_pointer_updated", "source_files_modified",
))
_FIELDS = _SOURCE_FIELDS | _COMPLETION_FLAGS | {"review_sha256"}
_HEX_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


def _sha_valid(value: object) -> bool:
    return type(value) is str and _HEX_DIGEST.fullmatch(value) is not None


def _bound_string(value: object) -> bool:
    return type(value) is str and 0 < len(value) <= 256


def review_deletion_preview_binding_dev(
    project_id: str, selected_paths: list[str], preview: dict, *,
    expected_generation: str | None = None,
    expected_source_revision: str | None = None,
) -> dict:
    """Check supplied preview semantics without trusting its provenance.

    expected_generation/source_revision are *caller-supplied* comparisons,
    not independent pins to the installed RAG runtime.
    """
    selection = review_explicit_deletion_paths_dev(project_id, selected_paths)
    if (type(preview) is not dict or set(preview) != _FIELDS):
        raise ValueError("unknown or missing preview fields")
    if any(preview[key] is not False for key in _COMPLETION_FLAGS):
        raise ValueError("preview carries an operational or mutation claim")
    if (type(preview["schema_version"]) is not int
        or preview["schema_version"] != 1
        or preview["mode"] != "READ_ONLY_REMOVAL_PREVIEW"
        or not _bound_string(preview["generation"])
        or not _bound_string(preview["source_revision"])
        or not _sha_valid(preview["review_sha256"])
        or type(preview["selected_paths"]) is not list
        or any(type(s) is not str for s in preview["selected_paths"])
        or any(type(preview[key]) is not int or preview[key] < 0
               for key in (
                    "documents_to_remove", "chunks_to_remove",
                    "documents_to_preserve", "chunks_to_preserve"
               ))
        or (preview["documents_to_remove"] > 0
            and preview["chunks_to_remove"] == 0)
        or preview["documents_to_remove"] != len(preview["selected_paths"])):
        raise ValueError("invalid read-only preview contract")
    for label, value in (
        ("expected_generation", expected_generation),
        ("expected_source_revision", expected_source_revision),
    ):
        if value is not None and not _bound_string(value):
            raise ValueError("invalid caller-supplied expected version: " + label)

    original = {name: preview[name] for name in _SOURCE_FIELDS}
    canonical_hash = sha256(json.dumps(
        original, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    sorted_paths = sorted(selected_paths)
    checks = {
        "project_id_matches_selection": preview["project_id"] == project_id,
        "exact_sorted_paths_match_selection": preview["selected_paths"] == sorted_paths,
        "document_count_matches_selection":
            preview["documents_to_remove"] == selection["count"],
        "preview_digest_matches_canonical_payload":
            preview["review_sha256"] == canonical_hash,
        "caller_expected_generation_matches":
            expected_generation is not None
            and preview["generation"] == expected_generation,
        "caller_expected_revision_matches":
            expected_source_revision is not None
            and preview["source_revision"] == expected_source_revision,
    }
    blockers = [name.upper() + "_UNVERIFIED" for name, ok in checks.items() if not ok]
    # No field in this document provides an authoritative filesystem proof.
    blockers.extend((
        "PREVIEW_PROVENANCE_NOT_INDEPENDENTLY_AUTHENTICATED",
        "LIVE_MANIFEST_SQLITE_AND_QDRANT_NOT_PINNED",
        "INSTALLED_GUI_AND_IPC_NOT_ATTESTED",
        "OPERATOR_CONFIRMATION_NOT_OBTAINED",
        "OPERATIONAL_DELETION_BLOCKED",
    ))
    return {
        "schema": "RAG_DEL_F16_DEV_PREVIEW_SELECTION_BINDING_V1",
        "state": ("F16_DEV_PREVIEW_FIELDS_COHERENT_NO_AUTHORITY"
                  if all(checks.values()) else "F16_DEV_PREVIEW_MISMATCH"),
        "checks": checks,
        "selection_sha256": selection["selection_sha256"],
        "review_sha256": preview["review_sha256"],
        "blockers": blockers,
        "source_only": True,
        "read_only": True,
        "preview_origin_authenticated": False,
        "current_generation_attested": False,
        "ready_for_operational_pilot": False,
        "activation_authorized": False,
        "operational_use_allowed": False,
    }
