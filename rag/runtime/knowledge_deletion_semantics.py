"""RAG-DEL: independently verify survivor vectors against candidate manifest.

Caller supplies an already-open *isolated* Qdrant client. No filesystem
opening, writes, catalog changes, or activation are performed here.
"""
from __future__ import annotations
from pathlib import Path

from rag.index.manifest import load_index_manifest
from rag.runtime.auto_index_incremental_plan import IncrementalPlanError
from rag.runtime.auto_index_incremental_batches import partition_reuse_receipt
from rag.runtime.auto_index_incremental_read import read_reusable_vectors
from rag.runtime.knowledge_deletion_structure import inspect_deletion_generation_structure


def verify_candidate_vector_semantics(
    stage_path: str | Path, project_id: str, staging_client, *,
    max_batch: int = 256,
) -> dict:
    if project_id == "codebridge" or not isinstance(project_id, str) or not project_id:
        raise IncrementalPlanError("public or missing private project")
    if staging_client is None or not isinstance(max_batch, int) or isinstance(max_batch, bool) or not 1 <= max_batch <= 256:
        raise IncrementalPlanError("invalid isolated vector client or batch size")
    stage = Path(stage_path)
    if not stage.is_dir() or stage.is_symlink():
        raise IncrementalPlanError("isolated stage is missing")
    manifest_path = stage / "rag-index-manifest.json"
    entries = tuple(load_index_manifest(manifest_path).entries)
    if any(entry.project_id != project_id for entry in entries):
        raise IncrementalPlanError("foreign project manifest")
    sources = [{"path": entry.path, "sha256": entry.sha256,
                "index_kind": entry.index_kind.value} for entry in entries]
    by_path = {entry.path: list(entry.chunk_ids) for entry in entries}
    if len(by_path) != len(entries):
        raise IncrementalPlanError("duplicate manifest paths")
    total = sum(len(ids) for ids in by_path.values())
    inspect_deletion_generation_structure(stage, project_id, total)
    receipt = {"mode": "CHUNK_RECEIPT_ONLY", "project_id": project_id,
               "candidate_chunk_ids": by_path, "candidate_vector_count": total,
               "vector_copy_authorized": False}
    batches = partition_reuse_receipt(receipt, {"sources": sources}, max_vectors=max_batch)
    checked = 0
    for batch in batches:
        records = read_reusable_vectors(staging_client, batch, {"sources": sources},
                                        max_vectors=max_batch)
        checked += sum(len(records[k]) for k in ("TEXT", "CODE"))
    if checked != total:
        raise IncrementalPlanError("candidate vector completeness failed")
    # Also reject extra vectors beyond the candidate's manifest.
    for kind in ("text", "code"):
        count = staging_client.count(collection_name=kind, exact=True).count
        expected = sum(len(e.chunk_ids) for e in entries if e.index_kind.value.lower() == kind)
        if count != expected:
            raise IncrementalPlanError("candidate contains unlisted vectors")
    return {"state": "CANDIDATE_VECTOR_SEMANTICS_VERIFIED",
            "project_id": project_id, "vectors_verified": checked,
            "documents_verified": len(entries), "activation_authorized": False,
            "catalog_modified": False}

