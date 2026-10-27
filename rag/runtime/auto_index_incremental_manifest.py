"""RAG-AUTO-05-C: verified-manifest reuse eligibility (no vector copying)."""
from __future__ import annotations

from pathlib import Path

from rag.index.manifest import load_index_manifest
from rag.runtime.auto_index_incremental_plan import IncrementalPlanError, _inventory


def inspect_reusable_manifest_chunks(
    verified_generation: dict, reviewed_sources: dict,
    eligible_paths: list[str], *,
    text_model_revision: str, code_model_revision: str,
) -> dict:
    """Return chunk IDs suitable for *further* Qdrant integrity validation.

    This is never authorization to copy or publish vectors. Callers must
    independently check collection/dimension/payload/ID provenance.
    """
    if not isinstance(verified_generation, dict) or verified_generation.get("verified") is not True:
        raise IncrementalPlanError("generation has not been verified")
    base = verified_generation.get("generation")
    if not isinstance(base, str) or not base:
        raise IncrementalPlanError("verified generation path missing")
    if (not isinstance(eligible_paths, list)
            or any(not isinstance(path, str) for path in eligible_paths)
            or len(eligible_paths) != len(set(eligible_paths))):
        raise IncrementalPlanError("invalid reuse candidate list")
    if not isinstance(text_model_revision, str) or not text_model_revision.strip():
        raise IncrementalPlanError("invalid text model revision")
    if not isinstance(code_model_revision, str) or not code_model_revision.strip():
        raise IncrementalPlanError("invalid code model revision")
    if not isinstance(reviewed_sources, dict):
        raise IncrementalPlanError("invalid approved source receipt")
    reviewed = _inventory({
        "schema_version": 1,
        "sources": reviewed_sources.get("sources"),
    })
    if any(path not in reviewed for path in eligible_paths):
        raise IncrementalPlanError("unreviewed path proposed for reuse")

    folder = Path(base)
    if folder.is_symlink() or (hasattr(folder, "is_junction") and folder.is_junction()):
        raise IncrementalPlanError("redirected verified generation")
    manifest_path = folder / "rag-index-manifest.json"
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise IncrementalPlanError("missing verified manifest")
    manifest = load_index_manifest(manifest_path)
    by_path = {}
    for entry in manifest.entries:
        if entry.path in by_path:
            raise IncrementalPlanError("duplicate manifest source path")
        by_path[entry.path] = entry

    mapping = {}
    observed_ids = set()
    for path in sorted(eligible_paths):
        entry = by_path.get(path)
        digest, kind = reviewed[path]
        expected_model = code_model_revision if kind == "CODE" else text_model_revision
        if (entry is None or entry.sha256 != digest
                or entry.index_kind.value != kind
                or entry.model_version != expected_model
                or entry.project_id != verified_generation.get("project_id")
                or not entry.chunk_ids):
            raise IncrementalPlanError("source manifest is ineligible for reuse")
        if observed_ids.intersection(entry.chunk_ids):
            raise IncrementalPlanError("shared chunk identifier across sources")
        observed_ids.update(entry.chunk_ids)
        mapping[path] = list(entry.chunk_ids)
    return {
        "schema_version": 1,
        "mode": "CHUNK_RECEIPT_ONLY",
        "project_id": verified_generation.get("project_id"),
        "candidate_chunk_ids": mapping,
        "candidate_vector_count": len(observed_ids),
        "qdrant_vectors_verified": False,
        "vector_copy_authorized": False,
        "public_pointer_updated": False,
    }
