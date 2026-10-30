"""RAG-DEL-01.03-A: stage SQLite/FTS/manifest removal in a NEW private directory.

Never mutate the active generation, source files, vectors, or catalog.
The returned staging directory is INCOMPLETE and MUST NOT be activated.
"""
from __future__ import annotations

from contextlib import closing
from pathlib import Path
import shutil
import sqlite3

from rag.index.fts5 import initialize_fts5
from rag.index.manifest import IndexManifest, load_index_manifest, save_index_manifest
from rag.runtime.knowledge_deletion_preview import (
    KnowledgeDeletionPreviewError, preview_knowledge_removal,
)
from rag.runtime.isolated_project_index import resolve_isolated_project


class DeletionStageError(RuntimeError):
    pass


def stage_removal_sqlite_manifest(project_id: str, selected_paths: list[str],
                                  expected_sha256: str, destination: str | Path) -> dict:
    """Materialize only an isolated SQLite/FTS/manifest candidate; never activate."""
    preview = preview_knowledge_removal(project_id, selected_paths)
    if not isinstance(expected_sha256, str) or preview["review_sha256"] != expected_sha256:
        raise DeletionStageError("stale deletion preview fingerprint")
    index = resolve_isolated_project(project_id)
    if (index is None or index.generation != preview["generation"]
            or index.source_revision != preview["source_revision"]):
        raise DeletionStageError("isolated generation changed")
    output = Path(destination)
    if output.exists() or output.is_symlink():
        raise DeletionStageError("destination must not exist")
    root = Path(index.sqlite).parent.resolve(strict=True)
    resolved = output.resolve()
    if resolved == root or root in resolved.parents or resolved in root.parents:
        raise DeletionStageError("destination overlaps active generation")
    source = Path(index.sqlite)
    manifest_path = Path(index.manifest)
    removed = set(preview["selected_paths"])
    manifest = load_index_manifest(manifest_path)
    if any(entry.project_id != project_id for entry in manifest.entries):
        raise DeletionStageError("mixed-project manifest is not supported")
    created = False
    try:
        output.mkdir(parents=False)
        created = True
        staged_db = output / "rag_index.sqlite3"
        staged_manifest = output / "rag-index-manifest.json"
        with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as original:
            with closing(sqlite3.connect(staged_db)) as candidate:
                original.backup(candidate)
                candidate.execute("PRAGMA foreign_keys=ON")
                with candidate:
                    selected_docs = candidate.execute(
                        "SELECT document_id FROM rag_documents WHERE project_id=? "
                        "AND path IN (" + ",".join("?" for _ in removed) + ")",
                        (project_id, *sorted(removed)),
                    ).fetchall()
                    if len(selected_docs) != len(removed):
                        raise DeletionStageError("staged document inventory changed")
                    ids = [row[0] for row in selected_docs]
                    for document_id in ids:
                        candidate.execute(
                            "DELETE FROM rag_chunk_symbols WHERE chunk_id IN "
                            "(SELECT chunk_id FROM rag_chunks WHERE document_id=?)",
                            (document_id,),
                        )
                        candidate.execute(
                            "DELETE FROM rag_chunks WHERE document_id=?", (document_id,)
                        )
                        candidate.execute(
                            "DELETE FROM rag_documents WHERE document_id=?", (document_id,)
                        )
                    initialize_fts5(candidate, rebuild=True)
                    documents = candidate.execute(
                        "SELECT count(*) FROM rag_documents WHERE project_id=?", (project_id,)
                    ).fetchone()[0]
                    chunks = candidate.execute(
                        "SELECT count(*) FROM rag_chunks WHERE project_id=?", (project_id,)
                    ).fetchone()[0]
                    candidate.execute(
                        "UPDATE rag_index_state SET document_count=?,chunk_count=? "
                        "WHERE project_id=?", (documents, chunks, project_id)
                    )
                if candidate.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise DeletionStageError("staged SQLite integrity failure")
                fts_count = candidate.execute(
                    "SELECT count(*) FROM rag_chunks_fts WHERE project_id=?", (project_id,)
                ).fetchone()[0]
                if (documents != preview["documents_to_preserve"]
                        or chunks != preview["chunks_to_preserve"] or fts_count != chunks):
                    raise DeletionStageError("staged SQLite/FTS count mismatch")
        kept = tuple(e for e in manifest.entries if e.path not in removed)
        if len(kept) != documents:
            raise DeletionStageError("staged manifest count mismatch")
        save_index_manifest(staged_manifest, IndexManifest(kept))
        return {"state": "SQLITE_MANIFEST_STAGED_NOT_VERIFIED",
                "project_id": project_id, "destination": str(output),
                "documents": documents, "chunks": chunks, "fts_chunks": fts_count,
                "vectors_copied": False, "activated": False,
                "public_pointer_updated": False}
    except BaseException:
        if created:
            shutil.rmtree(output)
        raise
