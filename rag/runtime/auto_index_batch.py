"""RAG-AUTO-02.3: deterministic, resumable vector batch selection.

Qdrant is the source of truth. The indexer sees only missing chunk IDs and
never publishes or reads/writes the public generation's index.
"""
from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3

from rag.index.qdrant_local import (
    open_qdrant_local,close_qdrant_local,
    TEXT_VECTOR_COLLECTION,CODE_VECTOR_COLLECTION,
)
from rag.runtime.auto_index_staging import stage_directory
from rag.runtime.auto_index_queue import get_job,AutoIndexQueueError

_COLUMNS=(
    "chunk_id,document_id,content,source_type,path,line_start,line_end,"
    "sha256,git_branch,git_commit"
)


def _read_qdrant_ids(client, collection: str, project_id: str) -> dict[str,dict]:
    found={}
    cursor=None
    while True:
        rows,cursor=client.scroll(
            collection_name=collection,limit=200,offset=cursor,
            with_payload=True,with_vectors=False,
        )
        for point in rows:
            payload=point.payload or {}
            chunk=payload.get("chunk_id")
            if not isinstance(chunk,str) or not chunk or (
                payload.get("project_namespace")!=project_id
            ):
                raise AutoIndexQueueError("foreign or invalid point in isolated Qdrant stage")
            if chunk in found:
                raise AutoIndexQueueError("duplicate chunk ID in Qdrant collection")
            found[chunk]=payload
        if cursor is None:
            break
    return found


def inventory_auto_vectors(queue_path: Path,job_id: str) -> dict:
    """Validate Qdrant IDs/payloads against SQLite, including source SHA."""
    job=get_job(queue_path,job_id)
    if job is None or not job["approved"]:
        raise PermissionError("job does not have an approved source snapshot")
    stage=stage_directory(queue_path,job_id)
    if not (stage/"rag_index.sqlite3").is_file() or not (stage/"qdrant").is_dir():
        raise AutoIndexQueueError("isolated stage not prepared")
    with closing(sqlite3.connect(
        f"{(stage/'rag_index.sqlite3').as_uri()}?mode=ro",uri=True,
    )) as cn:
        rows=cn.execute(
            f"SELECT {_COLUMNS} FROM rag_chunks WHERE project_id=? "
            "ORDER BY path,ordinal",(job["project_id"],),
        ).fetchall()
        docs=cn.execute(
            "SELECT count(*) FROM rag_documents WHERE project_id=?",
            (job["project_id"],),
        ).fetchone()[0]
    by_id={row[0]:row for row in rows}
    if len(by_id)!=len(rows) or not by_id:
        raise AutoIndexQueueError("staged SQLite has missing or duplicate chunks")
    client=open_qdrant_local(stage/"qdrant")
    try:
        text=_read_qdrant_ids(client,TEXT_VECTOR_COLLECTION,job["project_id"])
        code=_read_qdrant_ids(client,CODE_VECTOR_COLLECTION,job["project_id"])
    finally:
        close_qdrant_local(client)
    if not text.keys().isdisjoint(code):
        raise AutoIndexQueueError("same chunk appeared in both vector collections")
    for collection,completed in ((TEXT_VECTOR_COLLECTION,text),
                                 (CODE_VECTOR_COLLECTION,code)):
        for chunk,metadata in completed.items():
            stored=by_id.get(chunk)
            if (stored is None or
                (stored[3]=="CODE")!=(collection==CODE_VECTOR_COLLECTION) or
                metadata.get("document_id")!=stored[1] or
                metadata.get("source_type")!=stored[3] or
                metadata.get("path")!=stored[4] or
                metadata.get("sha256")!=stored[7] or
                metadata.get("content")!=stored[2]):
                raise AutoIndexQueueError("Qdrant point drifted from staged SQLite")
    expected_text=sum(row[3]!="CODE" for row in rows)
    expected_code=len(rows)-expected_text
    return {
        "stage":str(stage),"project_id":job["project_id"],"documents":docs,
        "chunks":len(rows),"expected_text":expected_text,
        "expected_code":expected_code,
        "text_done":len(text),"code_done":len(code),
        "total_done":len(text)+len(code),
        "complete":len(text)+len(code)==len(rows),
        "text_ids":set(text),"code_ids":set(code),
        "_rows":rows,
    }


def select_auto_vector_batch(
    queue_path: Path,job_id: str, *,max_vectors: int=256,
    prefer: str="TEXT",
) -> dict:
    """Select at most one model per batch; never re-embed persisted chunk IDs."""
    if type(max_vectors) is not int or not 1<=max_vectors<=256:
        raise ValueError("vector batch size must be between 1 and 256")
    if prefer not in ("TEXT","CODE"):
        raise ValueError("prefer must be TEXT or CODE")
    state=inventory_auto_vectors(queue_path,job_id)
    if state["complete"]:
        return {"state":"ALL_PRESENT","rows":[],"collection":None,
                "inventory":state}
    candidates=(prefer,"CODE" if prefer=="TEXT" else "TEXT")
    for kind in candidates:
        ids=state["code_ids"] if kind=="CODE" else state["text_ids"]
        selected=[
            row for row in state["_rows"]
            if (row[3]=="CODE")==(kind=="CODE") and row[0] not in ids
        ][:max_vectors]
        if selected:
            return {"state":"BATCH_SELECTED","rows":selected,
                    "collection":kind,"inventory":state}
    raise AutoIndexQueueError("missing chunks cannot be located")
