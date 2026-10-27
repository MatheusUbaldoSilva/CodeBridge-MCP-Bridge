"""RAG-AUTO-05-E: bounded vector import into an already isolated staging client.

Never opens a database or public index. Caller owns lifecycle and rollback.
The target must be empty for each imported point, and verified records are
required before any upsert. This is NOT a public generation promotion.
"""
from __future__ import annotations

from rag.runtime.auto_index_incremental_plan import IncrementalPlanError
from rag.runtime.auto_index_incremental_vectors import validate_reusable_point_records


def import_verified_reuse_batch(
    destination, receipt: dict, sources: dict, records: dict, *,
    isolated_destination: bool = False, allow_stage_write: bool = False,
    max_vectors: int = 256,
) -> dict:
    if isolated_destination is not True or allow_stage_write is not True:
        raise PermissionError("isolated destination and explicit stage authorization required")
    if not isinstance(max_vectors, int) or isinstance(max_vectors, bool) or not 1 <= max_vectors <= 256:
        raise IncrementalPlanError("invalid bounded batch size")
    proof = validate_reusable_point_records(receipt, sources, records)
    if proof["checked_vectors"] > max_vectors:
        raise IncrementalPlanError("vector batch exceeds safety limit")
    if destination is None:
        raise IncrementalPlanError("destination client absent")
    nonempty = sum(bool(records[kind]) for kind in ("TEXT", "CODE"))
    if nonempty != 1:
        raise IncrementalPlanError("exactly one model collection per atomic batch")
    from qdrant_client import models
    for kind, collection in (("TEXT", "text"), ("CODE", "code")):
        points = records[kind]
        if not points:
            continue
        point_ids = [point["id"] for point in points]
        existing = destination.retrieve(
            collection_name=collection, ids=point_ids,
            with_payload=False, with_vectors=False,
        )
        if existing:
            raise IncrementalPlanError("staging destination has existing point IDs")
    # All read-only preflight checks must finish before the first upsert.
    written = 0
    for kind, collection in (("TEXT", "text"), ("CODE", "code")):
        points = records[kind]
        if points:
            destination.upsert(
                collection_name=collection,
                points=[models.PointStruct(
                    id=item["id"], vector=item["vector"], payload=item["payload"],
                ) for item in points],
                wait=True,
            )
            written += len(points)
    return {
        "mode": "ISOLATED_STAGE_BATCH_WRITTEN",
        "vectors_written": written,
        "public_pointer_updated": False,
        "requires_staging_revalidation": True,
        "requires_checkpoint": True,
        "generation_activated": False,
    }
