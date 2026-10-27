"""RAG-AUTO-05-D: validate provided Qdrant vector records before any reuse.

Pure validator: points must be obtained separately from an isolated verified
generation. Validation does NOT read Qdrant, mutate indexes, or authorize copy.
"""
from __future__ import annotations

import math

from rag.index.vector_ids import deterministic_vector_point_id
from rag.models.embedding import TEXT_EMBEDDING_DIMENSION
from rag.models.code_embedding import CODE_EMBEDDING_DIMENSION
from rag.runtime.auto_index_incremental_plan import IncrementalPlanError, _inventory


_DIMENSIONS = {"TEXT": TEXT_EMBEDDING_DIMENSION, "CODE": CODE_EMBEDDING_DIMENSION}


def validate_reusable_point_records(
    receipt: dict, approved_source_receipt: dict, records: dict,
) -> dict:
    """Enforce project, collection, point IDs, source SHA and vector dimensions."""
    if not isinstance(receipt, dict) or receipt.get("mode") != "CHUNK_RECEIPT_ONLY":
        raise IncrementalPlanError("invalid chunk receipt")
    if receipt.get("vector_copy_authorized") is not False:
        raise IncrementalPlanError("unexpected prior authorization")
    project = receipt.get("project_id")
    chunks = receipt.get("candidate_chunk_ids")
    if not isinstance(chunks, dict) or not isinstance(records, dict):
        raise IncrementalPlanError("missing chunk or record map")
    sources = _inventory({"schema_version": 1,
                          "sources": approved_source_receipt.get("sources")})
    expected = {}
    for path, ids in chunks.items():
        if path not in sources or not isinstance(ids, list):
            raise IncrementalPlanError("unreviewed source in receipt")
        sha, kind = sources[path]
        for chunk in ids:
            if not isinstance(chunk, str) or not chunk or chunk in expected:
                raise IncrementalPlanError("ambiguous chunk ID")
            expected[chunk] = (path, sha, kind)
    if set(records) != {"TEXT", "CODE"}:
        raise IncrementalPlanError("records must contain separate text/code collections")
    observed = set()
    for kind, collection in (("TEXT", "text"), ("CODE", "code")):
        points = records[kind]
        if not isinstance(points, list):
            raise IncrementalPlanError("invalid point batch")
        for point in points:
            if not isinstance(point, dict):
                raise IncrementalPlanError("invalid point record")
            meta = point.get("payload")
            if not isinstance(meta, dict):
                raise IncrementalPlanError("missing point payload")
            chunk = meta.get("chunk_id")
            if not isinstance(chunk, str) or chunk not in expected or chunk in observed:
                raise IncrementalPlanError("foreign or duplicate vector")
            path, digest, expected_kind = expected[chunk]
            expected_source_type = (
                "CODE" if expected_kind == "CODE" else
                "LOG" if path.lower().endswith((".txt", ".log")) else "DOCUMENTATION"
            )
            if (kind != expected_kind or meta.get("path") != path
                    or meta.get("sha256") != digest
                    or meta.get("project_namespace") != project
                    or meta.get("source_type") != expected_source_type):
                raise IncrementalPlanError("vector provenance mismatch")
            try:
                expected_point_id = deterministic_vector_point_id(
                    project, collection, chunk)
            except ValueError as exc:
                raise IncrementalPlanError("invalid project namespace") from exc
            if point.get("id") != expected_point_id:
                raise IncrementalPlanError("vector point ID mismatch")
            vector = point.get("vector")
            if (not isinstance(vector, (list, tuple))
                    or len(vector) != _DIMENSIONS[kind]
                    or any(type(value) not in (float, int) or
                           not math.isfinite(value) for value in vector)):
                raise IncrementalPlanError("vector shape/value mismatch")
            observed.add(chunk)
    if observed != set(expected):
        raise IncrementalPlanError("missing candidate vectors")
    return {
        "mode": "VECTOR_RECEIPTS_VERIFIED",
        "checked_vectors": len(observed),
        "source_count": len(chunks),
        "validation_only": True,
        "copy_executed": False,
        "public_pointer_updated": False,
    }
