"""Offline-only Qdrant merge into a NEW isolated destination.

Inputs must be stable closed snapshots, NEVER a live production directory.
No production publication is performed.
"""
from __future__ import annotations
from pathlib import Path
import shutil
from rag.index.qdrant_local import open_qdrant_local, close_qdrant_local

COLLECTIONS = ("text", "code")


class IncrementalQdrantError(RuntimeError):
    pass


def _points(client, collection):
    offset = None
    while True:
        page, offset = client.scroll(
            collection_name=collection, limit=128, offset=offset,
            with_payload=True, with_vectors=True,
        )
        for point in page:
            yield point
        if offset is None:
            break


def stage_incremental_qdrant(existing, incoming, destination, project_id):
    old, stage, output = (Path(x).resolve() for x in (existing, incoming, destination))
    if len({old, stage, output}) != 3 or output.exists():
        raise IncrementalQdrantError("destination must be new and distinct")
    if not old.is_dir() or not stage.is_dir():
        raise IncrementalQdrantError("both closed Qdrant snapshots must exist")
    if not project_id:
        raise IncrementalQdrantError("project_id required")
    shutil.copytree(old, output)
    merged = open_qdrant_local(output)
    incoming_client = None
    try:
        incoming_client = open_qdrant_local(stage)
        added = 0
        from qdrant_client import models
        incoming_by_collection = {}
        incoming_docs = set()
        for collection in COLLECTIONS:
            if not incoming_client.collection_exists(collection):
                raise IncrementalQdrantError("missing incoming collection: " + collection)
            if not merged.collection_exists(collection):
                raise IncrementalQdrantError("missing original collection: " + collection)
            old_spec = merged.get_collection(collection).config.params.vectors
            new_spec = incoming_client.get_collection(collection).config.params.vectors
            if old_spec != new_spec:
                raise IncrementalQdrantError("vector schema mismatch: " + collection)
            points = list(_points(incoming_client, collection))
            if any((p.payload or {}).get("project_namespace") != project_id for p in points):
                raise IncrementalQdrantError("candidate includes another project")
            doc_ids = {p.payload.get("document_id") for p in points}
            if None in doc_ids:
                raise IncrementalQdrantError("candidate missing document_id")
            incoming_by_collection[collection] = points
            incoming_docs.update(doc_ids)
        for collection in COLLECTIONS:
            if incoming_docs:
                # Delete old chunks of updated docs in isolated copy, not production.
                merged.delete(
                    collection_name=collection,
                    points_selector=models.FilterSelector(filter=models.Filter(must=[
                        models.FieldCondition(key="project_namespace", match=models.MatchValue(value=project_id)),
                        models.FieldCondition(key="document_id", match=models.MatchAny(any=list(incoming_docs))),
                    ])),
                    wait=True,
                )
            points = incoming_by_collection[collection]
            if points:
                for pos in range(0, len(points), 64):
                    batch = points[pos:pos+64]
                    merged.upsert(
                        collection_name=collection,
                        points=[models.PointStruct(id=p.id, vector=p.vector, payload=p.payload) for p in batch],
                        wait=True,
                    )
                added += len(points)
        return {"state":"QDRANT_STAGED_NOT_PUBLISHED", "incoming_vectors":added,
                "incoming_documents":len(incoming_docs), "destination":str(output)}
    except BaseException:
        try:
            if incoming_client is not None:
                close_qdrant_local(incoming_client)
                incoming_client = None
            close_qdrant_local(merged)
            merged = None
        finally:
            shutil.rmtree(output, ignore_errors=True)
        raise
    finally:
        if incoming_client is not None:
            close_qdrant_local(incoming_client)
        if merged is not None:
            close_qdrant_local(merged)
