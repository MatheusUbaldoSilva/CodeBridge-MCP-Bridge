"""Project-scoped RAG index deletion for RAG-015-E.

This module deletes only derived index data.  It never receives a project source
root and never unlinks, rewrites, or otherwise mutates original source files.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3
from typing import Any, Optional

from .manifest import load_index_manifest, save_index_manifest
from .qdrant_local import (
    CODE_VECTOR_COLLECTION,
    TEXT_VECTOR_COLLECTION,
    QdrantLocalError,
)
from .vector_namespace import (
    build_project_namespace_filter,
    require_project_namespace,
)


@dataclass(frozen=True)
class ProjectIndexDeletionResult:
    project_id: str
    sqlite_documents_deleted: int
    sqlite_chunks_deleted: int
    sqlite_symbols_deleted: int
    sqlite_state_deleted: int
    text_vectors_deleted: int
    code_vectors_deleted: int
    manifest_entries_deleted: int

    @property
    def total_vectors_deleted(self) -> int:
        return self.text_vectors_deleted + self.code_vectors_deleted

    @property
    def total_sqlite_rows_deleted(self) -> int:
        return (
            self.sqlite_documents_deleted
            + self.sqlite_chunks_deleted
            + self.sqlite_symbols_deleted
            + self.sqlite_state_deleted
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "project_id": self.project_id,
            "sqlite_documents_deleted": self.sqlite_documents_deleted,
            "sqlite_chunks_deleted": self.sqlite_chunks_deleted,
            "sqlite_symbols_deleted": self.sqlite_symbols_deleted,
            "sqlite_state_deleted": self.sqlite_state_deleted,
            "text_vectors_deleted": self.text_vectors_deleted,
            "code_vectors_deleted": self.code_vectors_deleted,
            "manifest_entries_deleted": self.manifest_entries_deleted,
            "total_vectors_deleted": self.total_vectors_deleted,
            "total_sqlite_rows_deleted": self.total_sqlite_rows_deleted,
        }


def _require_connection(connection: sqlite3.Connection) -> None:
    if not isinstance(connection, sqlite3.Connection):
        raise ValueError("connection must be sqlite3.Connection")


def _count_one(
    connection: sqlite3.Connection,
    sql: str,
    parameters: tuple[object, ...],
) -> int:
    row = connection.execute(sql, parameters).fetchone()
    return int(row[0]) if row is not None else 0


def _sqlite_project_counts(
    connection: sqlite3.Connection,
    project_id: str,
) -> tuple[int, int, int, int]:
    documents = _count_one(
        connection,
        "SELECT COUNT(*) FROM rag_documents WHERE project_id = ?",
        (project_id,),
    )
    chunks = _count_one(
        connection,
        "SELECT COUNT(*) FROM rag_chunks WHERE project_id = ?",
        (project_id,),
    )
    symbols = _count_one(
        connection,
        """
        SELECT COUNT(*)
        FROM rag_chunk_symbols AS s
        JOIN rag_chunks AS c
          ON c.chunk_id = s.chunk_id
        WHERE c.project_id = ?
        """,
        (project_id,),
    )
    state = _count_one(
        connection,
        "SELECT COUNT(*) FROM rag_index_state WHERE project_id = ?",
        (project_id,),
    )
    return documents, chunks, symbols, state


def _vector_project_count(
    client: Any,
    collection_name: str,
    project_id: str,
) -> int:
    if client is None:
        raise ValueError("vector_client must not be None")

    try:
        exists = bool(client.collection_exists(collection_name))
    except Exception as exc:
        raise QdrantLocalError(
            f"failed to inspect collection {collection_name}"
        ) from exc

    if not exists:
        return 0

    project_filter = build_project_namespace_filter(project_id)
    try:
        result = client.count(
            collection_name=collection_name,
            count_filter=project_filter,
            exact=True,
        )
    except Exception as exc:
        raise QdrantLocalError(
            f"failed to count project points in {collection_name}"
        ) from exc
    return int(result.count)


def _delete_vector_project(
    client: Any,
    collection_name: str,
    project_id: str,
) -> int:
    before = _vector_project_count(
        client,
        collection_name,
        project_id,
    )
    if before == 0:
        return 0

    try:
        from qdrant_client import models
    except Exception as exc:
        raise QdrantLocalError(
            "qdrant-client models are required for project deletion"
        ) from exc

    project_filter = build_project_namespace_filter(project_id)
    try:
        client.delete(
            collection_name=collection_name,
            points_selector=models.FilterSelector(
                filter=project_filter,
            ),
            wait=True,
        )
    except Exception as exc:
        raise QdrantLocalError(
            f"failed to delete project points from {collection_name}"
        ) from exc

    remaining = _vector_project_count(
        client,
        collection_name,
        project_id,
    )
    if remaining != 0:
        raise QdrantLocalError(
            f"project vector deletion left {remaining} points "
            f"in {collection_name}"
        )
    return before


def _remove_manifest_project(
    manifest_path: Optional[str | Path],
    project_id: str,
) -> int:
    if manifest_path is None:
        return 0

    path = Path(manifest_path)
    if not path.exists():
        return 0

    manifest = load_index_manifest(path)
    before = len(manifest.entries)
    updated = manifest.remove_project(project_id)
    deleted = before - len(updated.entries)
    if deleted:
        save_index_manifest(path, updated)
    return deleted


def delete_project_index(
    connection: sqlite3.Connection,
    vector_client: Any,
    project_id: str,
    *,
    manifest_path: Optional[str | Path] = None,
) -> ProjectIndexDeletionResult:
    """Delete one project's derived RAG index without touching source files."""

    _require_connection(connection)
    project = require_project_namespace(project_id)
    if vector_client is None:
        raise ValueError("vector_client must not be None")

    documents, chunks, symbols, state = _sqlite_project_counts(
        connection,
        project,
    )

    # Vector collections are shared.  Delete by mandatory namespace filter;
    # never drop the collection itself because other projects may coexist.
    text_vectors = _delete_vector_project(
        vector_client,
        TEXT_VECTOR_COLLECTION,
        project,
    )
    code_vectors = _delete_vector_project(
        vector_client,
        CODE_VECTOR_COLLECTION,
        project,
    )

    try:
        connection.execute("BEGIN")
        connection.execute(
            "DELETE FROM rag_documents WHERE project_id = ?",
            (project,),
        )
        connection.execute(
            "DELETE FROM rag_index_state WHERE project_id = ?",
            (project,),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise

    remaining = _sqlite_project_counts(connection, project)
    if any(remaining):
        raise RuntimeError(
            "project SQLite deletion left residual rows: "
            f"documents={remaining[0]} chunks={remaining[1]} "
            f"symbols={remaining[2]} state={remaining[3]}"
        )

    manifest_entries = _remove_manifest_project(
        manifest_path,
        project,
    )

    return ProjectIndexDeletionResult(
        project_id=project,
        sqlite_documents_deleted=documents,
        sqlite_chunks_deleted=chunks,
        sqlite_symbols_deleted=symbols,
        sqlite_state_deleted=state,
        text_vectors_deleted=text_vectors,
        code_vectors_deleted=code_vectors,
        manifest_entries_deleted=manifest_entries,
    )
