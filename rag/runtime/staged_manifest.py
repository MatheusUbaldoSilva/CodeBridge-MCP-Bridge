"""Complete an isolated staged index with a verifiable manifest.

Never writes the active index. File drift during embedding fails closed.
"""
from __future__ import annotations

from pathlib import Path
import sqlite3

from rag.chunking.provenance import source_sha256
from rag.index.manifest import (
    IndexManifest, ManifestEntry, ManifestIndexKind,
    load_index_manifest, save_index_manifest,
)
from rag.runtime.status import resolve_rag_manifest_path


def create_staged_manifest(staging_root, project_root, project_id: str) -> dict:
    staged = Path(staging_root).resolve()
    project = Path(project_root).resolve()
    db = sqlite3.connect((staged / "rag_index.sqlite3").resolve().as_uri() + "?mode=ro", uri=True)
    try:
        docs = db.execute(
            "SELECT document_id, project_id, path, source_type, sha256 FROM rag_documents"
        ).fetchall()
        chunks = db.execute(
            "SELECT document_id, chunk_id FROM rag_chunks ORDER BY document_id, ordinal"
        ).fetchall()
    finally:
        db.close()
    by_document = {}
    for document_id, chunk in chunks:
        by_document.setdefault(document_id, []).append(chunk)
    entries = []
    if not docs:
        manifest = IndexManifest()
        save_index_manifest(staged / "rag-index-manifest.json", manifest)
        return {"state": "STAGED_MANIFEST_NOT_PUBLISHED", "entries": 0, "chunks": 0}
    active = load_index_manifest(resolve_rag_manifest_path())
    versions = {}
    for entry in active.entries:
        if entry.project_id == project_id:
            versions.setdefault(entry.index_kind, set()).add(entry.model_version)
    if not versions or any(len(values) != 1 for values in versions.values()):
        raise ValueError("ambiguous or unavailable active embedding model versions")
    for document_id, owner, relative, source_type, digest in docs:
        if owner != project_id:
            raise PermissionError("staged index contains other project")
        file = (project / relative).resolve(strict=True)
        if not file.is_relative_to(project) or not file.is_file():
            raise PermissionError("staged source escapes approved project")
        current = source_sha256(file.read_text(encoding="utf-8", errors="replace"))
        if current != digest:
            raise ValueError("source changed during staged vector indexing")
        kind = ManifestIndexKind.CODE if source_type == "CODE" else ManifestIndexKind.TEXT
        candidates = versions.get(kind, set())
        if len(candidates) != 1:
            raise ValueError("active index has no compatible model version")
        info = file.stat()
        entries.append(ManifestEntry(
            project_id=project_id,
            index_kind=kind,
            path=relative,
            size=info.st_size,
            mtime_ns=info.st_mtime_ns,
            sha256=digest,
            chunk_ids=tuple(by_document.get(document_id, ())),
            model_version=next(iter(candidates)),
        ))
    target = staged / "rag-index-manifest.json"
    if target.exists():
        raise FileExistsError("staged manifest already exists")
    manifest = IndexManifest(entries=tuple(entries))
    save_index_manifest(target, manifest)
    return {"state": "STAGED_MANIFEST_NOT_PUBLISHED", "entries": len(entries),
            "chunks": sum(len(entry.chunk_ids) for entry in entries)}