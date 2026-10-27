"""RAG-AUTO-05-E deterministic single-model bounded vector receipt partition."""
from __future__ import annotations

from rag.runtime.auto_index_incremental_plan import IncrementalPlanError,_inventory


def partition_reuse_receipt(
    receipt: dict, reviewed_sources: dict, *, max_vectors: int = 256,
) -> list[dict]:
    if not isinstance(receipt,dict) or receipt.get("mode")!="CHUNK_RECEIPT_ONLY":
        raise IncrementalPlanError("invalid reusable chunk receipt")
    if not isinstance(max_vectors,int) or isinstance(max_vectors,bool) or not 1 <= max_vectors <= 256:
        raise IncrementalPlanError("invalid vector batch size")
    if not isinstance(reviewed_sources,dict):
        raise IncrementalPlanError("missing reviewed source inventory")
    approved=_inventory({"schema_version":1,
                         "sources":reviewed_sources.get("sources")})
    references=receipt.get("candidate_chunk_ids")
    if not isinstance(references,dict):
        raise IncrementalPlanError("chunk IDs missing")
    unique=set()
    chunks={"TEXT":[],"CODE":[]}
    for path in sorted(references):
        if path not in approved:
            raise IncrementalPlanError("unapproved path in chunk receipt")
        values=references[path]
        if not isinstance(values,list) or not values:
            raise IncrementalPlanError("no chunk IDs for source")
        kind=approved[path][1]
        for chunk in values:
            if not isinstance(chunk,str) or not chunk or chunk in unique:
                raise IncrementalPlanError("duplicate or invalid chunk ID")
            unique.add(chunk)
            chunks[kind].append((path,chunk))
    if receipt.get("candidate_vector_count")!=len(unique):
        raise IncrementalPlanError("candidate chunk count mismatch")
    result=[]
    for kind in ("TEXT","CODE"):
        for offset in range(0,len(chunks[kind]),max_vectors):
            part=chunks[kind][offset:offset+max_vectors]
            selected={}
            for path,chunk in part:
                selected.setdefault(path,[]).append(chunk)
            result.append({
                "mode":"CHUNK_RECEIPT_ONLY",
                "project_id":receipt.get("project_id"),
                "candidate_chunk_ids":selected,
                "candidate_vector_count":len(part),
                "vector_copy_authorized":False,
                "batch_model":kind,
                "requires_provenance_verification":True,
            })
    return result
