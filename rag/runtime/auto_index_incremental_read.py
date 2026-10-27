"""RAG-AUTO-05-E: read-only bounded Qdrant receipt extraction.

Caller must supply an already verified, isolated source client. No production
collection is opened implicitly. Every retrieved point is checked again by
the existing payload and dimensional provenance validator.
"""
from __future__ import annotations

from rag.index.vector_ids import deterministic_vector_point_id
from rag.runtime.auto_index_incremental_plan import IncrementalPlanError, _inventory
from rag.runtime.auto_index_incremental_vectors import validate_reusable_point_records


def read_reusable_vectors(
    source_client, chunk_receipt: dict, reviewed_sources: dict, *,
    max_vectors: int = 256,
) -> dict:
    if source_client is None:
        raise IncrementalPlanError("source Qdrant client missing")
    if (not isinstance(max_vectors,int) or isinstance(max_vectors,bool)
            or not 1 <= max_vectors <= 256):
        raise IncrementalPlanError("invalid vector read limit")
    if (not isinstance(chunk_receipt,dict)
            or chunk_receipt.get("mode") != "CHUNK_RECEIPT_ONLY"
            or chunk_receipt.get("vector_copy_authorized") is not False):
        raise IncrementalPlanError("missing verified chunk receipt")
    if not isinstance(reviewed_sources,dict):
        raise IncrementalPlanError("invalid source approval")
    project=chunk_receipt.get("project_id")
    by_source=chunk_receipt.get("candidate_chunk_ids")
    if not isinstance(by_source,dict):
        raise IncrementalPlanError("missing source chunk references")
    kinds=_inventory({"schema_version":1,"sources":reviewed_sources.get("sources")})
    identifiers={"TEXT":[],"CODE":[]}
    for path, ids in by_source.items():
        if path not in kinds or not isinstance(ids,list):
            raise IncrementalPlanError("unreviewed vector source")
        kind=kinds[path][1]
        for chunk in ids:
            if not isinstance(chunk,str) or not chunk:
                raise IncrementalPlanError("invalid chunk identifier")
            identifiers[kind].append(deterministic_vector_point_id(
                project,kind.lower(),chunk,
            ))
    total=sum(len(ids) for ids in identifiers.values())
    if total > max_vectors:
        raise IncrementalPlanError("bounded read limit exceeded")
    records={"TEXT":[],"CODE":[]}
    for kind in ("TEXT","CODE"):
        if not identifiers[kind]:
            continue
        items=source_client.retrieve(
            collection_name=kind.lower(),ids=identifiers[kind],
            with_payload=True,with_vectors=True,
        )
        records[kind]=[
            {"id":str(item.id),"payload":item.payload,
             "vector":item.vector} for item in items
        ]
    validate_reusable_point_records(chunk_receipt,reviewed_sources,records)
    return records
