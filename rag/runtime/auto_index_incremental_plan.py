"""RAG-AUTO-05-A: deterministic read-only source delta contract.

Compares frozen approved inventories. This module never opens a production
index, starts Jina, changes a catalog, or assumes vector reuse is safe.
"""
from __future__ import annotations

from pathlib import PurePosixPath
import re

_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_KINDS = frozenset(("CODE", "TEXT"))
_MAX_SOURCES = 2000


class IncrementalPlanError(ValueError):
    """Refuse an ambiguous or untrusted incremental inventory."""


def _inventory(record: dict) -> dict[str, tuple[str, str]]:
    if not isinstance(record, dict) or record.get("schema_version") != 1:
        raise IncrementalPlanError("unsupported inventory schema")
    sources = record.get("sources")
    if not isinstance(sources, list) or len(sources) > _MAX_SOURCES:
        raise IncrementalPlanError("invalid source list")
    output = {}
    for item in sources:
        if not isinstance(item, dict) or set(item) != {"path", "sha256", "index_kind"}:
            raise IncrementalPlanError("unexpected source metadata")
        path, digest, kind = item["path"], item["sha256"], item["index_kind"]
        if not isinstance(path, str) or not path or "\\" in path:
            raise IncrementalPlanError("invalid source path")
        if len(path) > 1024 or ":" in path.split("/")[0] or chr(0) in path:
            raise IncrementalPlanError("unsafe source path spelling")
        canonical = PurePosixPath(path)
        if (canonical.is_absolute() or ".." in canonical.parts
                or canonical.as_posix() != path or path in output):
            raise IncrementalPlanError("unsafe or duplicate source path")
        if not isinstance(digest, str) or not _DIGEST.fullmatch(digest):
            raise IncrementalPlanError("invalid source SHA256")
        if not isinstance(kind, str) or kind not in _KINDS:
            raise IncrementalPlanError("invalid source kind")
        output[path] = (digest, kind)
    return output


def compare_frozen_inventories(
    baseline: dict, candidate: dict, *,
    baseline_text_model: str, candidate_text_model: str,
    baseline_code_model: str, candidate_code_model: str,
) -> dict:
    """Propose reuse; actual vectors still require separate integrity checks."""
    old, new = _inventory(baseline), _inventory(candidate)
    if not old:
        raise IncrementalPlanError("baseline cannot be empty")
    if not new:
        raise IncrementalPlanError("candidate cannot be empty")
    for name, value in (
        ("baseline_text_model", baseline_text_model),
        ("candidate_text_model", candidate_text_model),
        ("baseline_code_model", baseline_code_model),
        ("candidate_code_model", candidate_code_model),
    ):
        if not isinstance(value, str) or not value.strip() or len(value) > 256:
            raise IncrementalPlanError("missing model revision: " + name)

    unchanged, changed, added, removed, reuse = [], [], [], [], []
    for path in sorted(new):
        if path not in old:
            added.append(path)
        elif new[path] == old[path]:
            unchanged.append(path)
            _, kind = new[path]
            compatible = (
                baseline_text_model == candidate_text_model if kind == "TEXT"
                else baseline_code_model == candidate_code_model
            )
            if compatible:
                reuse.append(path)
            else:
                changed.append(path)
        else:
            changed.append(path)
    removed = sorted(set(old) - set(new))
    need_vectors = sorted(set(added + changed))
    return {
        "schema_version": 1,
        "mode": "PLAN_ONLY",
        "unchanged_sources": unchanged,
        "eligible_reuse_sources": sorted(reuse),
        "reindex_sources": need_vectors,
        "added_sources": added,
        "changed_or_incompatible_sources": sorted(changed),
        "removed_sources": removed,
        "counts": {
            "baseline": len(old), "candidate": len(new),
            "reusable": len(reuse), "reindex": len(need_vectors),
            "removed": len(removed),
        },
        "reuse_authorized": False,
        "requires_candidate_approval": True,
        "requires_vector_integrity_verification": True,
        "worker_started": False,
        "public_pointer_updated": False,
    }
