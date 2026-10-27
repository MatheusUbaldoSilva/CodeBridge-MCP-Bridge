"""RAG-AUTO-05-F strict read-only candidate SQLite match before Qdrant reuse."""
from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3

from rag.runtime.auto_index_incremental_plan import IncrementalPlanError


def verify_candidate_stage_rows(
    stage_db: Path, project_id: str, records: dict,
) -> dict:
    """No vector is valid unless the candidate's own SQLite confirms it."""
    db=Path(stage_db)
    if not db.is_file() or db.is_symlink():
        raise IncrementalPlanError("candidate staged SQLite missing/redirected")
    if not isinstance(records,dict) or set(records) != {"TEXT","CODE"}:
        raise IncrementalPlanError("invalid records for candidate database")
    ids={}
    for kind, items in records.items():
        if not isinstance(items,list):
            raise IncrementalPlanError("invalid candidate record group")
        for item in items:
            payload=item.get("payload") if isinstance(item,dict) else None
            if not isinstance(payload,dict):
                raise IncrementalPlanError("invalid candidate payload")
            chunk=payload.get("chunk_id")
            if not isinstance(chunk,str) or not chunk or chunk in ids:
                raise IncrementalPlanError("duplicate or invalid chunk identifier")
            ids[chunk]=(kind,payload)
    if not ids:
        raise IncrementalPlanError("candidate vector batch is empty")
    with closing(sqlite3.connect(db.as_uri()+"?mode=ro",uri=True,timeout=5)) as cn:
        # Use parameterized lookups, never interpolate source fields into SQL.
        for chunk,(kind,payload) in ids.items():
            row=cn.execute(
                "SELECT document_id,project_id,content,source_type,path,sha256 "
                "FROM rag_chunks WHERE chunk_id=?",(chunk,),
            ).fetchone()
            if row is None:
                raise IncrementalPlanError("chunk is missing from candidate stage")
            document,project,content,source_type,path,sha=row
            if (project!=project_id or payload.get("project_namespace")!=project_id
                    or payload.get("document_id")!=document
                    or payload.get("content")!=content
                    or payload.get("source_type")!=source_type
                    or payload.get("path")!=path
                    or payload.get("sha256")!=sha
                    or (kind=="CODE") != (source_type=="CODE")):
                raise IncrementalPlanError("candidate stage row differs from reused vector")
    return {"matched_rows":len(ids),"stage_matches_payload":True}
