"""RAG-DEL-01.03-B: bounded receipts for surviving vectors only.

Plan only. Does not open Qdrant, write vectors, or authorize promotion.
"""
from __future__ import annotations

from pathlib import Path
from rag.index.manifest import load_index_manifest
from rag.runtime.auto_index_incremental_batches import partition_reuse_receipt
from rag.runtime.auto_index_incremental_plan import IncrementalPlanError
from rag.runtime.knowledge_deletion_preview import preview_knowledge_removal
from rag.runtime.isolated_project_index import resolve_isolated_project


def plan_surviving_vector_batches(manifest_path: str | Path, preview: dict, *,
                                  max_vectors: int = 256) -> dict:
    if (not isinstance(preview, dict)
            or preview.get("mode") != "READ_ONLY_REMOVAL_PREVIEW"
            or preview.get("deletion_authorized") is not False
            or preview.get("candidate_created") is not False):
        raise IncrementalPlanError("untrusted deletion preview")
    project=preview.get("project_id")
    removed=preview.get("selected_paths")
    if (not isinstance(project,str) or project=="codebridge"
            or not isinstance(removed,list) or not removed
            or removed!=sorted(set(removed))):
        raise IncrementalPlanError("invalid deletion selection")
    current=preview_knowledge_removal(project,removed)
    if (current.get("review_sha256")!=preview.get("review_sha256")
            or current.get("generation")!=preview.get("generation")
            or current.get("source_revision")!=preview.get("source_revision")):
        raise IncrementalPlanError("stale generation or removal preview")
    path=Path(manifest_path)
    if path.resolve()!=Path(resolve_isolated_project(project).manifest).resolve():
        raise IncrementalPlanError("manifest is not the active isolated generation")
    if not path.is_file() or path.is_symlink():
        raise IncrementalPlanError("missing isolated manifest")
    manifest=load_index_manifest(path)
    entries=manifest.entries
    if any(entry.project_id!=project for entry in entries):
        raise IncrementalPlanError("foreign project in manifest")
    indexed={entry.path:entry for entry in entries}
    if len(indexed)!=len(entries) or not set(removed)<=set(indexed):
        raise IncrementalPlanError("invalid survivor inventory")
    survivors=[indexed[p] for p in sorted(set(indexed)-set(removed))]
    sources={"sources":[{"path":entry.path,"sha256":entry.sha256,
                          "index_kind":entry.index_kind.value}
                         for entry in survivors]}
    chunks={entry.path:list(entry.chunk_ids) for entry in survivors}
    total=sum(len(ids) for ids in chunks.values())
    if (total!=preview.get("chunks_to_preserve")
            or len(survivors)!=preview.get("documents_to_preserve")):
        raise IncrementalPlanError("preview/manifests drift")
    receipt={"mode":"CHUNK_RECEIPT_ONLY","project_id":project,
             "candidate_chunk_ids":chunks,"candidate_vector_count":total,
             "vector_copy_authorized":False}
    batches=partition_reuse_receipt(receipt,sources,max_vectors=max_vectors)
    return {"state":"SURVIVOR_RECEIPTS_ONLY","project_id":project,
            "source_revision":preview.get("source_revision"),
            "review_sha256":preview.get("review_sha256"),
            "sources":sources,"batches":batches,
            "vectors_to_preserve":total,"qdrant_opened":False,
            "vectors_copied":False,"activation_authorized":False}
