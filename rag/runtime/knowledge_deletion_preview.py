"""RAG-DEL-01.02: read-only preview for removing indexed knowledge.

No queue mutation, no model load, no Qdrant writes and no deletion.
"""
from __future__ import annotations

from contextlib import closing
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

from rag.runtime.isolated_project_index import resolve_isolated_project
from rag.index.manifest import load_index_manifest


class KnowledgeDeletionPreviewError(ValueError):
    pass


def preview_knowledge_removal(project_id: str, paths: list[str]) -> dict:
    if not isinstance(project_id, str) or project_id == "codebridge":
        raise KnowledgeDeletionPreviewError("public project cannot be modified")
    if (not isinstance(paths, list) or not paths
            or any(not isinstance(p, str) or not p or p.startswith(("/", "\\"))
                   or "\\" in p or "\\x00" in p or p in (".", "..")
                   or any(segment in ("", ".", "..") for segment in p.split("/"))
                   for p in paths)
            or len(paths) != len(set(paths))):
        raise KnowledgeDeletionPreviewError("invalid explicit file selection")
    index = resolve_isolated_project(project_id)
    if index is None:
        raise KnowledgeDeletionPreviewError("no enabled isolated project")
    db = Path(index.sqlite)
    if (not db.is_file() or db.is_symlink()
            or (hasattr(db, "is_junction") and db.is_junction())):
        raise KnowledgeDeletionPreviewError("unsafe index database")
    selected = sorted(paths)
    manifest_path = Path(index.manifest)
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise KnowledgeDeletionPreviewError("isolated manifest unavailable")
    manifest = load_index_manifest(manifest_path)
    entries = [entry for entry in manifest.entries if entry.project_id == project_id]
    manifest_paths = [entry.path for entry in entries]
    if len(manifest_paths) != len(set(manifest_paths)):
        raise KnowledgeDeletionPreviewError("duplicate manifest paths")
    by_path = {entry.path: entry for entry in entries}
    with closing(sqlite3.connect(db.as_uri() + "?mode=ro", uri=True, timeout=5)) as con:
        if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise KnowledgeDeletionPreviewError("database integrity failure")
        docs = con.execute(
            "SELECT path, COUNT(*) FROM rag_documents WHERE project_id=? GROUP BY path",
            (project_id,),
        ).fetchall()
        counts = dict(docs)
        if not all(counts.get(path) == 1 for path in selected):
            raise KnowledgeDeletionPreviewError("selected paths missing or duplicated")
        chunk_rows = con.execute(
            "SELECT path, COUNT(*) FROM rag_chunks WHERE project_id=? GROUP BY path",
            (project_id,),
        ).fetchall()
        chunks = dict(chunk_rows)
        if set(counts) != set(by_path):
            raise KnowledgeDeletionPreviewError("manifest/document path mismatch")
        if any(len(by_path[path].chunk_ids) != chunks.get(path, 0)
               for path in by_path):
            raise KnowledgeDeletionPreviewError("manifest/chunk count mismatch")
        if not all(chunks.get(path, 0) > 0 for path in selected):
            raise KnowledgeDeletionPreviewError("selected source missing chunks")
        total_chunks = sum(chunks.values())
        if set(chunks) != set(counts):
            raise KnowledgeDeletionPreviewError("document/chunk inventory mismatch")
    request = {
        "schema_version": 1,
        "mode": "READ_ONLY_REMOVAL_PREVIEW",
        "project_id": project_id,
        "generation": index.generation,
        "source_revision": index.source_revision,
        "selected_paths": selected,
        "documents_to_remove": len(selected),
        "chunks_to_remove": sum(chunks[p] for p in selected),
        "documents_to_preserve": len(counts) - len(selected),
        "chunks_to_preserve": total_chunks - sum(chunks[p] for p in selected),
    }
    request["review_sha256"] = sha256(
        json.dumps(request, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    request.update({
        "operator_approved": False,
        "deletion_authorized": False,
        "candidate_created": False,
        "public_pointer_updated": False,
        "source_files_modified": False,
    })
    return request
