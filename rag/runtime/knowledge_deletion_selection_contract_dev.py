"""F15 conservative lexical validation for a DEV file-deletion review.

No filesystem access and no integration into installed GUI. This is a
pre-review contract only, not evidence that selected files exist or belong to
a project. Windows-specific spellings are conservatively rejected.
"""
from __future__ import annotations

import hashlib
import json
import unicodedata

from rag.runtime.isolated_project_index import PROJECT_ID_PATTERN

_MAX_FILES = 500
_MAX_PATH_UTF8 = 4096
_MAX_TOTAL_UTF8 = 65536
_RESERVED = frozenset({
    "con", "prn", "aux", "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
})
_FORBIDDEN = frozenset('<>:"|?*') | {chr(92)}


def _validate_path(path: str) -> str:
    if type(path) is not str or not path or path.startswith("/"):
        raise ValueError("invalid explicit relative file path")
    if any(ord(c) < 32 or ord(c) == 127 for c in path):
        raise ValueError("control characters forbidden")
    if any(c in _FORBIDDEN for c in path):
        raise ValueError("unsafe Windows filename character")
    if any(unicodedata.category(c) in {"Cs", "Cf"} for c in path):
        raise ValueError("surrogates and format controls forbidden")
    if unicodedata.normalize("NFC", path) != path:
        raise ValueError("not NFC canonical")
    try:
        raw = path.encode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise ValueError("invalid Unicode") from exc
    if len(raw) > _MAX_PATH_UTF8:
        raise ValueError("path too long")
    parts = path.split("/")
    if any(
        not part or part in (".", "..")
        or part.endswith((".", " "))
        or part.split(".", 1)[0].casefold() in _RESERVED
        or any(ch in "‪‫‬‭‮⁦⁧⁨⁩" for ch in part)
        for part in parts
    ):
        raise ValueError("ambiguous or reserved path component")
    return path


def review_explicit_deletion_paths_dev(
    project_id: str, selected_paths: list[str],
) -> dict:
    """Validate paths and emit review receipt; permanently not authorized.

    This does not know index manifest, directory symlinks, real Windows
    normalization/NTFS semantics, or user approval. A valid lexical selection
    alone is not ready to delete.
    """
    # Source-of-truth namespace rule from the installed RAG isolated router:
    # never permit lexical-review IDs the actual router would reject.
    if (type(project_id) is not str or project_id == "codebridge"
        or PROJECT_ID_PATTERN.fullmatch(project_id) is None):
        raise ValueError("only routed private project identifiers accepted")
    if (type(selected_paths) is not list
        or not 1 <= len(selected_paths) <= _MAX_FILES):
        raise ValueError("selection size invalid")
    normalized = [_validate_path(path) for path in selected_paths]
    total = sum(len(path.encode("utf-8")) for path in normalized)
    if total > _MAX_TOTAL_UTF8:
        raise ValueError("selection exceeds size limit")
    # Conservative name collision key. Not a replica of filesystem case
    # rules; real path-to-file binding is a *separate* mandatory gate.
    keys = [unicodedata.normalize("NFKC", path).casefold() for path in normalized]
    if len(set(keys)) != len(keys):
        raise ValueError("ambiguous case/Unicode path aliases")
    for a in keys:
        if any(b.startswith(a + "/") for b in keys):
            raise ValueError("file selection contains ancestor/descendant alias")
    selected = sorted(normalized)
    payload = json.dumps(
        {"schema": "RAG_DEL_F15_LEXICAL_SELECTION_V1",
         "project": project_id, "paths": selected},
        ensure_ascii=True, sort_keys=True, separators=(",", ":"),
    ).encode("ascii")
    return {
        "state": "F15_DEV_LEXICAL_SELECTION_REVIEW_ONLY",
        "schema": "RAG_DEL_F15_LEXICAL_SELECTION_V1",
        "count": len(selected),
        "selection_sha256": hashlib.sha256(payload).hexdigest(),
        "selection_canonicalized": True,
        "paths_exposed_in_receipt": False,
        "blockers": [
            "LIVE_MANIFEST_AND_DOCUMENT_BINDING_NOT_ATTESTED",
            "SYMLINK_AND_REPARSE_POINT_RESOLUTION_NOT_ATTESTED",
            "CURRENT_GENERATION_AND_QUEUE_NOT_PINNED",
            "USER_FINAL_CONFIRMATION_NOT_OBTAINED",
            "OPERATIONAL_DELETION_NOT_AUTHORIZED",
        ],
        "read_only": True,
        "source_only": True,
        "ready_for_operational_pilot": False,
        "activation_authorized": False,
        "operational_use_allowed": False,
    }
