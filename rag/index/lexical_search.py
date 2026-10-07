"""Safe lexical search over the RAG FTS5 projection — RAG-005-C.

Queries are treated as literal FTS phrases, never as raw FTS syntax.
This phase deliberately does not define relevance score or BM25 ranking;
RAG-005-D owns lexical ranking.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
import sqlite3
from typing import List, Optional, Tuple

from rag.contracts import SearchQuery, SourceMetadata, SourceType

from .fts5 import FTS_TABLE, verify_fts5_integrity


_LEXICAL_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


class RagLexicalQueryError(ValueError):
    pass


@dataclass(frozen=True)
class LexicalSearchHit:
    chunk_id: str
    document_id: str
    content: str
    metadata: SourceMetadata
    ordinal: int
    title: Optional[str] = None
    heading_path: Optional[str] = None
    git_message: Optional[str] = None
    chunk_kind: Optional[str] = None
    parser_mode: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.chunk_id, str) or not self.chunk_id.strip():
            raise ValueError("chunk_id must be non-empty")
        if not isinstance(self.document_id, str) or not self.document_id.strip():
            raise ValueError("document_id must be non-empty")
        if not isinstance(self.content, str):
            raise ValueError("content must be a string")
        if not isinstance(self.metadata, SourceMetadata):
            raise ValueError("metadata must be SourceMetadata")
        if self.ordinal < 0:
            raise ValueError("ordinal must be >= 0")


def _literal_phrase(query: str) -> str:
    value = str(query or "").strip()
    if not value:
        raise RagLexicalQueryError("query must be non-empty")
    if not _LEXICAL_TOKEN_RE.search(value):
        raise RagLexicalQueryError(
            "query must contain at least one lexical token"
        )

    escaped = value.replace('"', '""')
    return f'"{escaped}"'


def _normalize_path_filter(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = str(value).strip().replace("\\", "/")
    if not normalized:
        raise RagLexicalQueryError(
            "path_filter must be non-empty when provided"
        )
    return normalized


def _escape_like(value: str) -> str:
    return (
        value
        .replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


def _source_type_clause(
    source_types: Tuple[SourceType, ...],
) -> Tuple[str, List[str]]:
    if not source_types:
        return "", []

    placeholders = ", ".join("?" for _ in source_types)
    return (
        f" AND c.source_type IN ({placeholders})",
        [item.value for item in source_types],
    )


def search_lexical(
    connection: sqlite3.Connection,
    query: SearchQuery,
) -> Tuple[LexicalSearchHit, ...]:
    """Search the FTS5 projection with literal phrase semantics.

    Result order is deterministic relational order only. It is not a
    relevance ranking policy.
    """

    if not isinstance(connection, sqlite3.Connection):
        raise ValueError("connection must be sqlite3.Connection")
    if not isinstance(query, SearchQuery):
        raise ValueError("query must be SearchQuery")

    verify_fts5_integrity(connection)

    match_query = _literal_phrase(query.query)
    path_filter = _normalize_path_filter(query.path_filter)

    sql = f"""
        SELECT
            c.chunk_id,
            c.document_id,
            c.content,
            c.project_id,
            c.source_type,
            c.path,
            c.symbol,
            c.line_start,
            c.line_end,
            c.git_branch,
            c.git_commit,
            c.sha256,
            c.indexed_at,
            c.source_id,
            c.ordinal,
            c.title,
            c.heading_path,
            c.git_message,
            c.chunk_kind,
            c.parser_mode
        FROM {FTS_TABLE} AS f
        JOIN rag_chunks AS c
          ON c.rowid = f.rowid
        WHERE {FTS_TABLE} MATCH ?
          AND c.project_id = ?
    """

    parameters: List[object] = [
        match_query,
        query.project_id,
    ]

    source_sql, source_parameters = _source_type_clause(
        query.source_types
    )
    sql += source_sql
    parameters.extend(source_parameters)

    if path_filter is not None:
        sql += (
            " AND c.path IS NOT NULL"
            " AND c.path LIKE ? ESCAPE '\\'"
        )
        parameters.append(
            f"%{_escape_like(path_filter)}%"
        )

    if query.branch is not None:
        branch = str(query.branch).strip()
        if not branch:
            raise RagLexicalQueryError(
                "branch must be non-empty when provided"
            )
        sql += " AND c.git_branch = ?"
        parameters.append(branch)

    sql += """
        ORDER BY
            c.document_id ASC,
            c.ordinal ASC,
            c.chunk_id ASC
        LIMIT ?
    """
    parameters.append(query.top_k)

    try:
        rows = connection.execute(
            sql,
            tuple(parameters),
        ).fetchall()
    except sqlite3.OperationalError as exc:
        raise RagLexicalQueryError(
            f"lexical search failed: {exc}"
        ) from exc

    hits: List[LexicalSearchHit] = []

    for row in rows:
        source_type = SourceType(str(row[4]))
        metadata = SourceMetadata(
            project_id=str(row[3]),
            source_type=source_type,
            path=row[5],
            symbol=row[6],
            line_start=row[7],
            line_end=row[8],
            git_branch=row[9],
            git_commit=row[10],
            sha256=row[11],
            indexed_at=row[12],
            source_id=row[13],
        )

        hits.append(
            LexicalSearchHit(
                chunk_id=str(row[0]),
                document_id=str(row[1]),
                content=str(row[2]),
                metadata=metadata,
                ordinal=int(row[14]),
                title=row[15],
                heading_path=row[16],
                git_message=row[17],
                chunk_kind=row[18],
                parser_mode=row[19],
            )
        )

    return tuple(hits)
