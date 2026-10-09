"""RAG-017-H: validate and publish a staged single-project RAG index.

The source project is not modified. Publication refuses to overwrite existing
production data; multi-project migration is a separate operation.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import shutil
import sqlite3

from rag.index.manifest import (
    IndexManifest, ManifestEntry, ManifestIndexKind, save_index_manifest,
)
from rag.index.qdrant_local import (
    open_qdrant_local, close_qdrant_local, TEXT_VECTOR_COLLECTION,
    CODE_VECTOR_COLLECTION, resolve_qdrant_local_path,
)
from rag.index.sqlite_schema import initialize_rag_schema
from rag.runtime.status import resolve_rag_manifest_path, resolve_rag_sqlite_path


class RagPublicationError(RuntimeError):
    pass


def validate_staged_index(staging: str | Path, project_id: str) -> dict:
    stage = Path(staging).resolve()
    db = stage / "rag_index.sqlite3"
    vectors = stage / "qdrant"
    if not db.is_file() or not vectors.is_dir():
        raise RagPublicationError("incomplete staging: SQLite or Qdrant missing")
    conn = sqlite3.connect(f"{db.as_uri()}?mode=ro", uri=True)
    try:
        docs = conn.execute("SELECT document_id,path,source_type,sha256 FROM rag_documents WHERE project_id=?", (project_id,)).fetchall()
        chunks = conn.execute("SELECT chunk_id,document_id,source_type,path FROM rag_chunks WHERE project_id=?", (project_id,)).fetchall()
        total_docs = conn.execute("SELECT count(*) FROM rag_documents").fetchone()[0]
        total_chunks = conn.execute("SELECT count(*) FROM rag_chunks").fetchone()[0]
        if not docs or len(docs) != total_docs or len(chunks) != total_chunks:
            raise RagPublicationError("staging empty or contains another project")
        known = {r[0] for r in docs}
        if any(r[1] not in known for r in chunks):
            raise RagPublicationError("orphan chunks in staging")
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RagPublicationError("SQLite integrity check failed")
    finally:
        conn.close()
    vector = open_qdrant_local(vectors)
    try:
        text_count = vector.count(collection_name=TEXT_VECTOR_COLLECTION,exact=True).count
        code_count = vector.count(collection_name=CODE_VECTOR_COLLECTION,exact=True).count
    finally:
        close_qdrant_local(vector)
    expected_text = sum(r[2] != "CODE" for r in chunks)
    expected_code = sum(r[2] == "CODE" for r in chunks)
    if text_count != expected_text or code_count != expected_code:
        raise RagPublicationError("vector count mismatch with SQLite chunks")
    return {"documents":len(docs),"chunks":len(chunks),"text_vectors":text_count,"code_vectors":code_count}


def publish_staged_index(staging: str | Path, project_id: str, project_root: str | Path) -> dict:
    """Publish only into an empty production directory; fail closed otherwise."""
    from rag.index.vector_namespace import require_project_namespace
    require_project_namespace(project_id)
    stage = Path(staging).resolve()
    root = Path(project_root).resolve()
    if not root.is_dir():
        raise RagPublicationError("source project root is unavailable")
    stats = validate_staged_index(stage,project_id)
    production_db = resolve_rag_sqlite_path()
    production_vector = resolve_qdrant_local_path()
    production_manifest = resolve_rag_manifest_path()
    paths = (production_db,production_vector,production_manifest)
    if any(p.exists() for p in paths):
        raise RagPublicationError("existing production index: explicit migration required")
    production_db.parent.mkdir(parents=True,exist_ok=True)
    db_copy = production_db.with_name(production_db.name + ".publishing")
    vector_copy = production_vector.with_name(production_vector.name + ".publishing")
    created=[]
    try:
        shutil.copy2(stage/"rag_index.sqlite3",db_copy)
        shutil.copytree(stage/"qdrant",vector_copy)
        conn=sqlite3.connect(str(db_copy))
        try:
            now=datetime.now(timezone.utc).isoformat()
            conn.execute(
                "INSERT INTO rag_index_state(project_id,state,schema_version,last_indexed_at,document_count,chunk_count) VALUES(?,?,?,?,?,?)",
                (project_id,"READY",1,now,stats["documents"],stats["chunks"]),
            )
            conn.commit()
        finally:
            conn.close()
        source=sqlite3.connect(f"{db_copy.resolve().as_uri()}?mode=ro",uri=True)
        try:
            documents=source.execute("SELECT document_id,path,source_type,sha256 FROM rag_documents").fetchall()
            entries=[]
            for document_id,path,source_type,sha in documents:
                chunk_ids=tuple(x[0] for x in source.execute(
                    "SELECT chunk_id FROM rag_chunks WHERE document_id=? ORDER BY ordinal",(document_id,)
                ))
                # Model revision is the configured pinned version, not a runtime generated value.
                if source_type=="CODE":
                    from rag.models.code_backend_policy import CODE_MODEL_REVISION
                    version=CODE_MODEL_REVISION
                    kind=ManifestIndexKind.CODE
                else:
                    from rag.models.backend_policy import TEXT_MODEL_REVISION
                    version=TEXT_MODEL_REVISION
                    kind=ManifestIndexKind.TEXT
                source_path=(root/path).resolve()
                if not source_path.is_relative_to(root) or not source_path.is_file():
                    raise RagPublicationError("source missing or outside project root")
                from rag.chunking.provenance import source_sha256
                if source_sha256(source_path.read_text(encoding="utf-8",errors="replace")) != sha:
                    raise RagPublicationError("source modified since staging")
                stat=source_path.stat()
                entries.append(ManifestEntry(project_id=project_id,index_kind=kind,path=path,size=stat.st_size,mtime_ns=stat.st_mtime_ns,sha256=sha,chunk_ids=chunk_ids,model_version=version))
        finally:
            source.close()
        # Publication sequence is guarded: manifest goes last, after both stores.
        db_copy.rename(production_db)
        created.append(production_db)
        vector_copy.rename(production_vector)
        created.append(production_vector)
        save_index_manifest(production_manifest,IndexManifest(tuple(entries)))
        created.append(production_manifest)
        return {"state":"READY","project_id":project_id,**stats}
    except BaseException:
        for path in reversed(created):
            if path.is_dir():
                shutil.rmtree(path)
            elif path.exists():
                path.unlink()
        raise
    finally:
        if db_copy.exists():
            db_copy.unlink()
        if vector_copy.exists():
            shutil.rmtree(vector_copy)
