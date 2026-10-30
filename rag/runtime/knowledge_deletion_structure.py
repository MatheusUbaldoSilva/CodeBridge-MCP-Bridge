"""Independent structural inspection of a private RAG-DEL generation candidate."""
from __future__ import annotations
from collections import defaultdict
from contextlib import closing
from pathlib import Path
import sqlite3

from rag.index.manifest import load_index_manifest

class DeletionCandidateStructureError(RuntimeError):
    pass

def inspect_deletion_generation_structure(generation:Path,project_id:str,
                                           expected_chunks:int)->dict:
    fail=DeletionCandidateStructureError
    root=Path(generation)
    db=root/"rag_index.sqlite3"
    manifest=root/"rag-index-manifest.json"
    if (not root.is_dir() or root.is_symlink() or not db.is_file()
            or db.is_symlink() or not manifest.is_file() or manifest.is_symlink()
            or type(expected_chunks) is not int or expected_chunks<0):
        raise fail("missing or redirected candidate artifacts")
    entries=load_index_manifest(manifest).entries
    if any(e.project_id!=project_id for e in entries):
        raise fail("mixed project manifest not allowed")
    listed={entry.path:entry for entry in entries}
    if len(listed)!=len(entries):
        raise fail("duplicate manifest paths")
    with closing(sqlite3.connect(db.as_uri()+"?mode=ro",uri=True,timeout=5)) as con:
        if con.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
            raise fail("SQLite integrity check failed")
        docs=con.execute(
            "SELECT path,sha256 FROM rag_documents WHERE project_id=? ORDER BY path",(project_id,)
        ).fetchall()
        chunk_rows=con.execute(
            "SELECT path,chunk_id FROM rag_chunks WHERE project_id=? ORDER BY path,ordinal",(project_id,)
        ).fetchall()
        other_docs=con.execute(
            "SELECT count(*) FROM rag_documents WHERE project_id!=?",(project_id,)
        ).fetchone()[0]
        other_chunks=con.execute(
            "SELECT count(*) FROM rag_chunks WHERE project_id!=?",(project_id,)
        ).fetchone()[0]
        fts=con.execute(
            "SELECT count(*) FROM rag_chunks_fts WHERE project_id=?",(project_id,)
        ).fetchone()[0]
        foreign_fts=con.execute(
            "SELECT count(*) FROM rag_chunks_fts WHERE project_id!=?",(project_id,)
        ).fetchone()[0]
    if other_docs or other_chunks or foreign_fts:
        raise fail("foreign project in private candidate")
    if len(docs)!=len(listed):
        raise fail("document inventory mismatch")
    if any(path not in listed or sha!=listed[path].sha256 for path,sha in docs):
        raise fail("document SHA or path mismatch")
    grouped=defaultdict(list)
    for path,cid in chunk_rows:
        grouped[path].append(cid)
    if set(grouped)!=set(listed) and listed:
        raise fail("chunk paths differ from manifest")
    if any(tuple(grouped[e.path])!=e.chunk_ids for e in entries):
        raise fail("chunk identities changed")
    if len(chunk_rows)!=expected_chunks or fts!=expected_chunks:
        raise fail("chunk or FTS count mismatch")
    return {"state":"DELETION_SQLITE_MANIFEST_STRUCTURALLY_VALID",
            "project_id":project_id,"documents":len(docs),
            "chunks":len(chunk_rows),"fts_chunks":fts,
            "activation_authorized":False}
