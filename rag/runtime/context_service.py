"""Authorized context retrieval for RAG-013-D."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3
from typing import Iterable, Optional, Tuple

from rag.index.vector_namespace import require_project_namespace
from rag.runtime.status import resolve_rag_sqlite_path
from rag.sources.exclusion_policy import classify_denied_path


MAX_CONTEXT_SELECTION = 100


class RagContextIndexUnavailableError(RuntimeError):
    pass


class RagContextSourceMissingError(RuntimeError):
    pass


class RagContextInvalidScopeError(ValueError):
    pass


@dataclass(frozen=True)
class RetrievedContext:
    chunk_id: str
    document_id: str
    project_id: str
    source_type: str
    content: str
    path: Optional[str]
    symbol: Optional[str]
    line_start: Optional[int]
    line_end: Optional[int]
    git_branch: Optional[str]
    git_commit: Optional[str]
    sha256: Optional[str]
    indexed_at: Optional[str]
    source_id: Optional[str]
    document_content: Optional[str] = None

    def to_dict(self) -> dict[str, object]:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "project_id": self.project_id,
            "source_type": self.source_type,
            "content": self.content,
            "path": self.path,
            "symbol": self.symbol,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "git_branch": self.git_branch,
            "git_commit": self.git_commit,
            "sha256": self.sha256,
            "indexed_at": self.indexed_at,
            "source_id": self.source_id,
            "document_content": self.document_content,
        }


@dataclass(frozen=True)
class GetContextResult:
    project_id: str
    items: Tuple[RetrievedContext, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "project_id": self.project_id,
            "count": len(self.items),
            "items": [item.to_dict() for item in self.items],
        }


def _validate_chunk_ids(chunk_ids: Iterable[str]) -> Tuple[str, ...]:
    values = tuple(chunk_ids)
    if not values:
        raise RagContextInvalidScopeError(
            "chunk_ids must contain at least one selected result"
        )
    if len(values) > MAX_CONTEXT_SELECTION:
        raise RagContextInvalidScopeError(
            f"chunk_ids exceeds maximum selection of {MAX_CONTEXT_SELECTION}"
        )
    if any(not isinstance(item, str) or not item.strip() for item in values):
        raise RagContextInvalidScopeError(
            "chunk_ids must contain non-empty strings"
        )
    if len(set(values)) != len(values):
        raise RagContextInvalidScopeError(
            "chunk_ids must not contain duplicates"
        )
    return values


def _open_read_only(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise RagContextIndexUnavailableError(
            f"RAG SQLite index is unavailable: {path}"
        )
    uri = f"{path.resolve().as_uri()}?mode=ro"
    try:
        return sqlite3.connect(uri, uri=True)
    except sqlite3.Error as exc:
        raise RagContextIndexUnavailableError(
            f"failed to open RAG SQLite index read-only: {exc}"
        ) from exc


def get_context(
    *,
    project_id: str,
    chunk_ids: Iterable[str],
    include_document_content: bool = False,
    sqlite_path: Optional[str | Path] = None,
) -> GetContextResult:
    project = require_project_namespace(project_id)
    selected = _validate_chunk_ids(chunk_ids)
    path = (
        Path(sqlite_path)
        if sqlite_path is not None
        else resolve_rag_sqlite_path()
    )

    connection = _open_read_only(path)
    try:
        items = []
        for chunk_id in selected:
            row = connection.execute(
                """
                SELECT
                    c.chunk_id,
                    c.document_id,
                    c.project_id,
                    c.source_type,
                    c.content,
                    c.path,
                    c.symbol,
                    c.line_start,
                    c.line_end,
                    c.git_branch,
                    c.git_commit,
                    c.sha256,
                    c.indexed_at,
                    c.source_id,
                    d.content
                FROM rag_chunks AS c
                JOIN rag_documents AS d
                    ON d.document_id = c.document_id
                WHERE c.chunk_id = ?
                  AND c.project_id = ?
                  AND d.project_id = ?
                """,
                (chunk_id, project, project),
            ).fetchone()

            if row is None:
                raise RagContextSourceMissingError(
                    f"selected chunk is unavailable in project {project}: {chunk_id}"
                )

            source_path = row[5]
            if source_path is not None:
                denied = classify_denied_path(str(source_path))
                if denied is not None:
                    raise RagContextInvalidScopeError(
                        f"selected chunk path is no longer authorized: "
                        f"{source_path} ({denied.value})"
                    )

            items.append(
                RetrievedContext(
                    chunk_id=str(row[0]),
                    document_id=str(row[1]),
                    project_id=str(row[2]),
                    source_type=str(row[3]),
                    content=str(row[4]),
                    path=row[5],
                    symbol=row[6],
                    line_start=row[7],
                    line_end=row[8],
                    git_branch=row[9],
                    git_commit=row[10],
                    sha256=row[11],
                    indexed_at=row[12],
                    source_id=row[13],
                    document_content=(
                        str(row[14])
                        if include_document_content
                        else None
                    ),
                )
            )
    except sqlite3.Error as exc:
        raise RagContextIndexUnavailableError(
            f"failed to read RAG context: {exc}"
        ) from exc
    finally:
        connection.close()

    return GetContextResult(
        project_id=project,
        items=tuple(items),
    )
