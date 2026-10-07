"""Minimum lexical ranking policy for RAG-005-D.

FTS5 BM25 is the only relevance signal in RAG-005.
Embeddings and hybrid fusion remain out of scope.
"""

from __future__ import annotations

import math
import sqlite3
from typing import List, Tuple

from rag.contracts import SearchQuery, SearchResult, SourceMetadata, SourceType

from .fts5 import FTS_TABLE, verify_fts5_integrity
from .lexical_search import (
    RagLexicalQueryError,
    _escape_like,
    _literal_phrase,
    _normalize_path_filter,
    _source_type_clause,
)


LEXICAL_RETRIEVAL_MODE = "LEXICAL_FTS5_BM25"

# FTS5 column order:
# chunk_id, document_id, project_id, content, path, symbol,
# git_message, title, heading_path
LEXICAL_BM25_WEIGHTS: Tuple[float, ...] = (
    0.0,
    0.0,
    0.0,
    1.0,
    3.0,
    6.0,
    2.0,
    4.0,
    3.0,
)


def lexical_score_from_bm25(value: float) -> float:
    """Convert FTS5 distance semantics into public higher-is-better score."""

    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError("bm25 value must be finite")
    return -numeric


def search_lexical_ranked(
    connection: sqlite3.Connection,
    query: SearchQuery,
) -> Tuple[SearchResult, ...]:
    """Return ranked lexical results using the frozen RAG-005-D policy."""

    if not isinstance(connection, sqlite3.Connection):
        raise ValueError("connection must be sqlite3.Connection")
    if not isinstance(query, SearchQuery):
        raise ValueError("query must be SearchQuery")

    verify_fts5_integrity(connection)

    match_query = _literal_phrase(query.query)
    path_filter = _normalize_path_filter(query.path_filter)

    weights_sql = ", ".join(
        repr(weight)
        for weight in LEXICAL_BM25_WEIGHTS
    )

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
            bm25({FTS_TABLE}, {weights_sql}) AS lexical_distance
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
            lexical_distance ASC,
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
            f"ranked lexical search failed: {exc}"
        ) from exc

    results: List[SearchResult] = []

    for rank, row in enumerate(rows, 1):
        metadata = SourceMetadata(
            project_id=str(row[3]),
            source_type=SourceType(str(row[4])),
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
        score = lexical_score_from_bm25(
            float(row[15])
        )

        results.append(
            SearchResult(
                chunk_id=str(row[0]),
                document_id=str(row[1]),
                content=str(row[2]),
                metadata=metadata,
                score=score,
                rank=rank,
                retrieval_modes=(
                    LEXICAL_RETRIEVAL_MODE,
                ),
                stale=False,
            )
        )

    return tuple(results)
