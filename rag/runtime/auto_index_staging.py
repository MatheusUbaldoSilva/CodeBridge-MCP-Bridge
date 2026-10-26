"""RAG-AUTO-02.2: prepare a resumable isolated staging generation.

No embeddings, model load, worker start, production write or publication.
Only a previously reviewed QUEUED job can create a per-job SQLite/Qdrant stage.
"""
from __future__ import annotations

from contextlib import closing
import json
import os
from pathlib import Path
import shutil
import sqlite3
from datetime import datetime, timezone

from rag.chunking.provenance import source_sha256
from rag.index.fts5 import initialize_fts5
from rag.index.manifest import (
    IndexManifest, ManifestEntry, ManifestIndexKind, save_index_manifest,
)
from rag.index.qdrant_local import (
    open_qdrant_local, close_qdrant_local, ensure_vector_collections,
)
from rag.index.sqlite_schema import connect_rag_index
from rag.index.vector_ids import deterministic_chunk_id, deterministic_document_id
from rag.models.backend_policy import TEXT_MODEL_REVISION
from rag.models.code_backend_policy import CODE_MODEL_REVISION
from rag.runtime.auto_index_approval import (
    read_reviewed_sources, revalidate_auto_index_preview, _source_hash,
)
from rag.runtime.auto_index_queue import (
    _canonical_queue_path, AutoIndexQueueError, get_job,
)
from rag.runtime.production_index import _drafts, _source_type


def stage_directory(queue_path: Path, job_id: str) -> Path:
    job=get_job(queue_path,job_id)
    if job is None:
        raise AutoIndexQueueError("job is not registered")
    queue=_canonical_queue_path(queue_path)
    auto_root=queue.parent.parent.resolve()
    root=Path(job["source_root"]).resolve(strict=True)
    if (root==auto_root or root.is_relative_to(auto_root)
            or auto_root.is_relative_to(root)):
        raise AutoIndexQueueError("source and isolated auto workspace overlap")
    stage=auto_root / "staging" / ("job-"+job_id)
    # A pre-existing reparse point may otherwise redirect the worker into a
    # different directory, potentially including the public RAG state.
    for candidate in (
        auto_root,stage.parent,stage,stage/"rag_index.sqlite3",
        stage/"qdrant",stage/"rag-index-manifest.json",stage/"progress.json",
    ):
        if candidate.is_symlink() or (
            hasattr(candidate,"is_junction") and candidate.is_junction()
        ):
            raise AutoIndexQueueError("redirected staging path forbidden")
        if candidate.exists() and not candidate.resolve().is_relative_to(auto_root):
            raise AutoIndexQueueError("staging path escaped isolated workspace")
    return stage


def _check_existing(stage: Path,job: dict,receipt: dict) -> dict:
    data=json.loads((stage/"progress.json").read_text(encoding="utf-8"))
    expected=receipt["review_sha256"]
    if (data.get("job_id")!=job["job_id"]
            or data.get("project_id")!=job["project_id"]
            or data.get("source_revision")!=expected
            or data.get("state")!="INDEXING_NOT_PUBLISHED"
            or data.get("published") is not False):
        raise AutoIndexQueueError("existing stage has a different source or state")
    if not (stage/"rag_index.sqlite3").is_file() or not (
        stage/"rag-index-manifest.json"
    ).is_file() or not (stage/"qdrant").is_dir():
        raise AutoIndexQueueError("existing stage incomplete")
    with closing(sqlite3.connect(f"{(stage/'rag_index.sqlite3').as_uri()}?mode=ro",uri=True)) as cn:
        docs=cn.execute("SELECT count(*) FROM rag_documents WHERE project_id=?",
                        (job["project_id"],)).fetchone()[0]
        chunks=cn.execute("SELECT count(*) FROM rag_chunks WHERE project_id=?",
                          (job["project_id"],)).fetchone()[0]
        integrity=cn.execute("PRAGMA integrity_check").fetchone()[0]
        text=cn.execute("SELECT count(*) FROM rag_chunks WHERE project_id=? AND source_type!='CODE'",
                        (job["project_id"],)).fetchone()[0]
        code=chunks-text
    if integrity!="ok" or docs!=len(receipt["sources"]) or chunks!=data.get("expected_chunks") or (
        text!=data.get("text_vectors_expected") or code!=data.get("code_vectors_expected")
    ):
        raise AutoIndexQueueError("staging SQLite has drifted")
    return {"job_id":job["job_id"],"stage":str(stage),"documents":docs,
            "chunks":chunks,"text_chunks":text,"code_chunks":code,
            "reused":True,"worker_started":False,"index_published":False}


def prepare_auto_staging(queue_path: Path,job_id: str, *,
                         operator_approved: bool=False,
                         preparation_enabled: bool=False) -> dict:
    """Create a new, unique stage for one approved job (no Jina inference)."""
    if operator_approved is not True or preparation_enabled is not True:
        raise PermissionError("staging requires explicit approved action")
    job=get_job(queue_path,job_id)
    if job is None or job["state"]!="QUEUED" or not job["approved"]:
        raise AutoIndexQueueError("stage requires an approved QUEUED job")
    receipt=read_reviewed_sources(queue_path,job_id)
    approved={
        "schema_version":1,
        "project_id":job["project_id"],"source_root":job["source_root"],
        "scope":job["requested_scope"],"sources":receipt["sources"],
        "review_sha256":receipt["review_sha256"],
    }
    revalidate_auto_index_preview(approved)
    stage=stage_directory(queue_path,job_id)
    if stage.exists():
        return _check_existing(stage,job,receipt)
    stage.parent.mkdir(parents=True,exist_ok=True)
    if stage.parent.is_symlink() or stage.is_symlink():
        raise AutoIndexQueueError("staging directory cannot be a symbolic link")
    temp=stage.with_name(stage.name+"-preparing")
    if temp.exists():
        raise AutoIndexQueueError("unfinished staging directory requires manual audit")
    temp.mkdir(parents=False,exist_ok=False)
    root=Path(job["source_root"]).resolve()
    db=None
    try:
        db=connect_rag_index(temp/"rag_index.sqlite3")
        manifest=[]
        chunks=0
        text_chunks=0
        code_chunks=0
        for item in receipt["sources"]:
            relative=item["path"]
            # Verify source bytes and policy again before ingestion.
            if _source_hash(root,relative)!=item["sha256"]:
                raise AutoIndexQueueError("approved source hash changed")
            file=(root/relative).resolve(strict=True)
            contents=file.read_bytes().decode("utf-8",errors="replace")
            from rag.sources.exclusion_policy import classify_denied_path
            from rag.sources.secret_detection import scan_sensitive_content
            if classify_denied_path(relative) is not None or scan_sensitive_content(
                contents,max_findings=1
            ).sensitive:
                raise AutoIndexQueueError("candidate became denied or sensitive")
            is_code=item["index_kind"]=="CODE"
            if item["index_kind"] not in ("CODE","TEXT"):
                raise AutoIndexQueueError("invalid index kind in review receipt")
            kind=ManifestIndexKind.CODE if is_code else ManifestIndexKind.TEXT
            source_type=_source_type(relative,is_code)
            did=deterministic_document_id(job["project_id"],source_type,relative)
            sha=source_sha256(contents)
            drafts=_drafts(relative,contents,is_code)
            if not drafts:
                raise AutoIndexQueueError("approved source produced zero chunks")
            db.execute(
                "INSERT INTO rag_documents(document_id,project_id,source_type,"
                "content,path,sha256,git_branch,git_commit) VALUES(?,?,?,?,?,?,?,?)",
                (did,job["project_id"],source_type.value,contents,relative,sha,None,None),
            )
            ids=[]
            for draft in drafts:
                cid=deterministic_chunk_id(did,int(draft.ordinal),draft.content)
                db.execute(
                    "INSERT INTO rag_chunks(chunk_id,document_id,project_id,ordinal,"
                    "content,source_type,path,line_start,line_end,sha256,git_branch,git_commit) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (cid,did,job["project_id"],int(draft.ordinal),draft.content,
                     source_type.value,relative,draft.line_start,draft.line_end,sha,None,None),
                )
                ids.append(cid)
                chunks+=1
                if is_code:
                    code_chunks+=1
                else:
                    text_chunks+=1
            stat=file.stat()
            manifest.append(ManifestEntry(
                project_id=job["project_id"],index_kind=kind,path=relative,
                size=stat.st_size,mtime_ns=stat.st_mtime_ns,sha256=sha,
                chunk_ids=tuple(ids),
                model_version=CODE_MODEL_REVISION if is_code else TEXT_MODEL_REVISION,
            ))
        db.commit()
        initialize_fts5(db,rebuild=True)
        db.execute(
            "INSERT INTO rag_index_state(project_id,state,schema_version,"
            "source_revision,document_count,chunk_count) VALUES(?,?,?,?,?,?)",
            (job["project_id"],"INDEXING",1,receipt["review_sha256"],
             len(manifest),chunks),
        )
        db.commit()
        integrity=db.execute("PRAGMA integrity_check").fetchone()[0]
        fts=db.execute("SELECT count(*) FROM rag_chunks_fts").fetchone()[0]
        if integrity!="ok" or fts!=chunks:
            raise AutoIndexQueueError("stage SQLite/FTS5 verification failed")
        db.close()
        db=None
        save_index_manifest(
            temp/"rag-index-manifest.json",IndexManifest(entries=tuple(manifest))
        )
        client=open_qdrant_local(temp/"qdrant")
        try:
            ensure_vector_collections(client)
        finally:
            close_qdrant_local(client)
        revalidate_auto_index_preview(approved)
        progress={
            "job_id":job_id,"project_id":job["project_id"],
            "source_revision":receipt["review_sha256"],
            "state":"INDEXING_NOT_PUBLISHED","published":False,
            "expected_chunks":chunks,"text_vectors_expected":text_chunks,
            "code_vectors_expected":code_chunks,
            "text_vectors_done":0,"code_vectors_done":0,"total_vectors_done":0,
            "last_batch_result":"STAGED_NO_VECTORS",
            "prepared_at":datetime.now(timezone.utc).isoformat(),
        }
        (temp/"progress.json").write_text(
            json.dumps(progress,sort_keys=True,indent=2)+"\n",encoding="utf-8"
        )
        # Final directory rename is the publication of the *isolated stage*,
        # never the public RAG generation.
        os.rename(temp,stage)
        return {"job_id":job_id,"stage":str(stage),"documents":len(manifest),
                "chunks":chunks,"text_chunks":text_chunks,"code_chunks":code_chunks,
                "reused":False,"worker_started":False,"index_published":False}
    except BaseException:
        if db is not None:
            db.close()
        if temp.exists():
            shutil.rmtree(temp,ignore_errors=True)
        raise
