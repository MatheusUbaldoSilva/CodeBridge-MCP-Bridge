"""RAG-DEL-01.03-C: independent read-only validation of a deletion candidate.

This is a structural QA report, NOT a generation receipt or activation grant.
"""
from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3

from rag.index.manifest import load_index_manifest
from rag.runtime.auto_index_incremental_read import read_reusable_vectors
from rag.runtime.auto_index_incremental_checkpoint import read_isolated_batch_receipt
from rag.runtime.auto_index_incremental_plan import IncrementalPlanError


def validate_deletion_candidate(stage_path: str | Path, plan: dict,
                                staging_client, batch_ids: list[str]) -> dict:
    if not isinstance(plan,dict) or plan.get("state")!="SURVIVOR_RECEIPTS_ONLY":
        raise IncrementalPlanError("invalid surviving vector plan")
    project=plan.get("project_id")
    batches=plan.get("batches")
    if (not isinstance(project,str) or project=="codebridge"
            or not isinstance(batches,list)
            or not isinstance(batch_ids,list) or len(batches)!=len(batch_ids)
            or len(batch_ids)!=len(set(batch_ids))):
        raise IncrementalPlanError("invalid batch inventory")
    stage=Path(stage_path)
    if not stage.is_dir() or stage.is_symlink() or (
        hasattr(stage,"is_junction") and stage.is_junction()
    ):
        raise IncrementalPlanError("missing isolated candidate directory")
    database=stage/"rag_index.sqlite3"
    manifest_path=stage/"rag-index-manifest.json"
    if (not database.is_file() or database.is_symlink()
            or not manifest_path.is_file() or manifest_path.is_symlink()):
        raise IncrementalPlanError("candidate sqlite or manifest unavailable")
    manifest=load_index_manifest(manifest_path)
    entries=manifest.entries
    if any(entry.project_id!=project for entry in entries):
        raise IncrementalPlanError("foreign namespace in candidate manifest")
    mapped={entry.path:entry for entry in entries}
    if len(mapped)!=len(entries):
        raise IncrementalPlanError("duplicate candidate manifest path")
    planned_sources=plan.get("sources",{}).get("sources")
    if not isinstance(planned_sources,list):
        raise IncrementalPlanError("planned source inventory missing")
    planned={row["path"]:row for row in planned_sources}
    if len(planned)!=len(planned_sources) or set(planned)!=set(mapped):
        raise IncrementalPlanError("candidate manifest differs from survivor plan")
    for path,entry in mapped.items():
        source=planned[path]
        if (entry.sha256!=source["sha256"] or
                entry.index_kind.value!=source["index_kind"]):
            raise IncrementalPlanError("candidate manifest source drift")
    with closing(sqlite3.connect(database.as_uri()+"?mode=ro",uri=True,timeout=5)) as cn:
        if cn.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
            raise IncrementalPlanError("candidate sqlite integrity failed")
        docs=cn.execute(
            "SELECT path,sha256 FROM rag_documents WHERE project_id=?",(project,)
        ).fetchall()
        chunks=cn.execute(
            "SELECT path,chunk_id FROM rag_chunks WHERE project_id=? ORDER BY ordinal",
            (project,)
        ).fetchall()
        fts=cn.execute(
            "SELECT count(*) FROM rag_chunks_fts WHERE project_id=?",(project,)
        ).fetchone()[0]
        other=cn.execute(
            "SELECT count(*) FROM rag_documents WHERE project_id!=?",(project,)
        ).fetchone()[0]
    if other or len(docs)!=len(mapped) or len(chunks)!=fts:
        raise IncrementalPlanError("candidate sqlite document/FTS mismatch")
    if len(chunks)!=plan.get("vectors_to_preserve"):
        raise IncrementalPlanError("candidate vector count drift")
    if any(path not in mapped or sha!=mapped[path].sha256 for path,sha in docs):
        raise IncrementalPlanError("candidate document provenance drift")
    chunk_map={p:[] for p in mapped}
    for path,chunk in chunks:
        if path not in chunk_map:
            raise IncrementalPlanError("orphan chunk path")
        chunk_map[path].append(chunk)
    if any(tuple(ids)!=mapped[p].chunk_ids for p,ids in chunk_map.items()):
        raise IncrementalPlanError("candidate chunk ID provenance drift")
    checked=0
    sources=plan["sources"]
    for receipt,bid in zip(batches,batch_ids):
        saved=read_isolated_batch_receipt(stage,bid)
        vectors=read_reusable_vectors(staging_client,receipt,sources)
        amount=sum(len(vectors[k]) for k in ("TEXT","CODE"))
        if amount!=saved["vectors_written"]:
            raise IncrementalPlanError("batch receipt and persisted vectors differ")
        checked+=amount
    if checked!=len(chunks):
        raise IncrementalPlanError("incomplete candidate vector readback")
    return {"state":"DELETION_STAGING_STRUCTURALLY_VALID",
            "project_id":project,"documents":len(docs),"chunks":len(chunks),
            "vectors_verified":checked,"batches_verified":len(batches),
            "generation_receipt_created":False,
            "activation_authorized":False,"public_pointer_updated":False}
