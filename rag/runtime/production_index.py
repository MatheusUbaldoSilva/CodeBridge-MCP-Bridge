"""Staged, isolated indexing executor; publication belongs to RAG-017-H."""
from __future__ import annotations

from pathlib import Path
import os
import shutil
import sqlite3
from uuid import uuid4

from rag.chunking import chunk_markdown, chunk_text_log, safe_chunk_code
from rag.chunking.provenance import source_sha256
from rag.contracts import SourceType
from rag.index.fts5 import initialize_fts5
from rag.index.sqlite_schema import connect_rag_index
from rag.index.vector_ids import deterministic_document_id, deterministic_chunk_id
from rag.runtime.index_request import RagIndexPlan
from rag.runtime.status import resolve_rag_sqlite_path


def _drafts(path: str, content: str, code: bool):
    if code:
        result = safe_chunk_code(content, path=path)
        return result.structural_chunks or result.fallback_chunks
    return chunk_markdown(content) if Path(path).suffix.lower()==".md" else chunk_text_log(content)


def _source_type(path: str, code: bool) -> SourceType:
    if code:
        return SourceType.CODE
    if Path(path).suffix.lower() in (".txt",".log"):
        return SourceType.LOG
    return SourceType.DOCUMENTATION


def build_staged_index(plan: RagIndexPlan) -> dict[str, object]:
    """Build a complete project-specific staging corpus and vectors, never publish it."""
    if not isinstance(plan, RagIndexPlan):
        raise ValueError("plan must be RagIndexPlan")
    root=Path(plan.project_root).resolve()
    from rag.sources.git_state import capture_git_head_state, GitStateError
    try:
        git_state=capture_git_head_state(root)
    except GitStateError:
        git_state=None
    branch=git_state.branch if git_state else None
    commit=git_state.head_commit if git_state else None
    state=resolve_rag_sqlite_path().parent
    staging=state/"staging"/("build-"+uuid4().hex)
    staging.mkdir(parents=True, exist_ok=False)
    db_path=staging/"rag_index.sqlite3"
    connection=connect_rag_index(db_path)
    documents=chunks=0
    try:
        for candidate in plan.candidates:
            path=(root/candidate.path).resolve()
            if not path.is_relative_to(root) or not path.is_file():
                raise ValueError("index candidate escaped or disappeared from project")
            # Recheck security immediately before writing each source.
            from rag.sources.exclusion_policy import classify_denied_path
            from rag.sources.secret_detection import scan_sensitive_content
            if classify_denied_path(candidate.path) is not None:
                raise ValueError("denied source in index plan")
            content=path.read_text(encoding="utf-8",errors="replace")
            if scan_sensitive_content(content,max_findings=1).sensitive:
                raise ValueError("sensitive source changed since plan creation")
            code=candidate.code_eligible
            source=_source_type(candidate.path,code)
            did=deterministic_document_id(plan.project_id,source,candidate.path)
            sha=source_sha256(content)
            connection.execute(
                "INSERT INTO rag_documents(document_id,project_id,source_type,content,path,sha256,git_branch,git_commit) VALUES(?,?,?,?,?,?,?,?)",
                (did,plan.project_id,source.value,content,candidate.path,sha,branch,commit),
            )
            documents+=1
            for draft in _drafts(candidate.path,content,code):
                cid=deterministic_chunk_id(did,int(draft.ordinal),draft.content)
                connection.execute(
                    "INSERT INTO rag_chunks(chunk_id,document_id,project_id,ordinal,content,source_type,path,line_start,line_end,sha256,git_branch,git_commit) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (cid,did,plan.project_id,int(draft.ordinal),draft.content,source.value,candidate.path,getattr(draft,"line_start",None),getattr(draft,"line_end",None),sha,branch,commit),
                )
                chunks+=1
        connection.commit()
        initialize_fts5(connection,rebuild=True)
        connection.commit()
        text_rows=connection.execute(
            "SELECT chunk_id,document_id,content,source_type,path,line_start,line_end,sha256,git_branch,git_commit FROM rag_chunks WHERE source_type != 'CODE' ORDER BY document_id,ordinal"
        ).fetchall()
        code_rows=connection.execute(
            "SELECT chunk_id,document_id,content,source_type,path,line_start,line_end,sha256,git_branch,git_commit FROM rag_chunks WHERE source_type = 'CODE' ORDER BY document_id,ordinal"
        ).fetchall()
        connection.close()
        connection=None
        from rag.runtime.production_search import _MODEL_LOCK
        with _MODEL_LOCK:
            _write_vectors(staging/"qdrant",plan.project_id,text_rows,code_rows)
        return {"state":"STAGED_NOT_PUBLISHED","project_id":plan.project_id,"staging_path":str(staging),"documents":documents,"chunks":chunks,"text_chunks":len(text_rows),"code_chunks":len(code_rows)}
    except BaseException:
        if connection is not None:
            connection.close()
            connection = None
        shutil.rmtree(staging,ignore_errors=True)
        raise
    finally:
        if connection is not None:
            connection.close()


def _write_vectors(path: Path, project_id: str, text_rows, code_rows) -> None:
    from qdrant_client import models
    from rag.index.qdrant_local import (
        open_qdrant_local,close_qdrant_local,ensure_vector_collections,
        TEXT_VECTOR_COLLECTION,CODE_VECTOR_COLLECTION,
    )
    from rag.index.vector_ids import deterministic_vector_point_id
    from rag.index.vector_namespace import vector_payload_with_namespace
    from rag.models.artifact_install import resolve_selected_model_path
    from rag.models.code_artifact_install import resolve_selected_code_model_path
    from rag.models.embedding import TextEmbeddingClient
    from rag.models.code_embedding import CodeEmbeddingClient,CodeRetrievalTask
    from rag.models.lifecycle import LlamaServerConfig,TextModelLifecycle
    from rag.models.code_lifecycle import CodeModelLifecycle,build_code_server_config

    client=open_qdrant_local(path)
    llama=Path(r"C:\llama\llama-server.exe")
    try:
        ensure_vector_collections(client)
        for rows,collection in ((text_rows,TEXT_VECTOR_COLLECTION),(code_rows,CODE_VECTOR_COLLECTION)):
            if not rows:
                continue
            if collection==TEXT_VECTOR_COLLECTION:
                life=TextModelLifecycle(LlamaServerConfig(executable_path=llama,model_path=resolve_selected_model_path(),port=0,gpu_layers=99,device="CUDA0"))
            else:
                life=CodeModelLifecycle(build_code_server_config(executable_path=llama,model_path=resolve_selected_code_model_path(),port=0,gpu_layers=99,device="CUDA0"))
            life.load(timeout_seconds=90)
            try:
                embed=TextEmbeddingClient(life) if collection==TEXT_VECTOR_COLLECTION else CodeEmbeddingClient(life)
                batch=[]
                for row in rows:
                    vector=(embed.embed_document(row[2]).values if collection==TEXT_VECTOR_COLLECTION
                            else embed.embed_passage(CodeRetrievalTask.NL2CODE,row[2]).values)
                    payload=vector_payload_with_namespace(project_id,{"document_id":row[1],"content":row[2],"source_type":row[3],"path":row[4],"line_start":row[5],"line_end":row[6],"sha256":row[7],"chunk_id":row[0],"git_branch":row[8],"git_commit":row[9]})
                    batch.append(models.PointStruct(id=deterministic_vector_point_id(project_id,collection,row[0]),vector=list(vector),payload=payload))
                    if len(batch)>=64:
                        client.upsert(collection_name=collection,points=batch,wait=True)
                        batch=[]
                if batch:
                    client.upsert(collection_name=collection,points=batch,wait=True)
            finally:
                life.unload(timeout_seconds=15)
    finally:
        close_qdrant_local(client)
