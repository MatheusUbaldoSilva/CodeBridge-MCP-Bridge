"""RAG-010-B â€” collect FTS5 and code-vector candidates without fusion.

RAG-010-D owns rank fusion and RAG-010-E owns deduplication.
This module deliberately returns the two ranked candidate lists separately.
"""

from __future__ import annotations

from dataclasses import dataclass
import sqlite3
from typing import Any, Optional, Sequence, Tuple

from rag.contracts import SearchQuery, SearchResult, SourceMetadata, SourceType
from rag.index.lexical_ranking import search_lexical_ranked
from rag.index.qdrant_local import CODE_VECTOR_COLLECTION
from rag.index.vector_namespace import build_project_namespace_filter
from rag.models.code_embedding import CODE_EMBEDDING_DIMENSION


CODE_VECTOR_RETRIEVAL_MODE = "VECTOR_CODE_COSINE"


@dataclass(frozen=True)
class CodeHybridCandidates:
    lexical: Tuple[SearchResult, ...]
    vector: Tuple[SearchResult, ...]

    def __post_init__(self) -> None:
        if any(not isinstance(item, SearchResult) for item in self.lexical):
            raise ValueError("lexical must contain SearchResult values")
        if any(not isinstance(item, SearchResult) for item in self.vector):
            raise ValueError("vector must contain SearchResult values")


def _payload_text(
    payload: dict[str, Any],
    key: str,
    *,
    required: bool = False,
) -> Optional[str]:
    value = payload.get(key)
    if value is None:
        if required:
            raise ValueError(f"vector payload requires {key}")
        return None
    if not isinstance(value, str):
        raise ValueError(f"vector payload {key} must be a string")
    if required and not value.strip():
        raise ValueError(f"vector payload {key} must be non-empty")
    return value


def _build_vector_filter(query: SearchQuery) -> Any:
    try:
        from qdrant_client import models
    except Exception as exc:
        raise RuntimeError(
            "qdrant-client is required for code vector search"
        ) from exc

    base = build_project_namespace_filter(query.project_id)
    must = list(base.must or [])

    if query.source_types:
        must.append(
            models.FieldCondition(
                key="source_type",
                match=models.MatchAny(
                    any=[item.value for item in query.source_types],
                ),
            )
        )

    if query.branch is not None:
        branch = str(query.branch).strip()
        if not branch:
            raise ValueError("branch must be non-empty when provided")
        must.append(
            models.FieldCondition(
                key="git_branch",
                match=models.MatchValue(value=branch),
            )
        )

    return models.Filter(must=must)


def _path_matches(
    payload: dict[str, Any],
    path_filter: Optional[str],
) -> bool:
    if path_filter is None:
        return True
    wanted = str(path_filter).strip().replace("\\", "/")
    if not wanted:
        raise ValueError("path_filter must be non-empty when provided")
    actual = payload.get("path")
    if not isinstance(actual, str):
        return False
    return wanted in actual.replace("\\", "/")


def _search_limit(
    client: Any,
    query: SearchQuery,
    qdrant_filter: Any,
) -> int:
    if query.path_filter is None:
        return query.top_k

    count = client.count(
        collection_name=CODE_VECTOR_COLLECTION,
        count_filter=qdrant_filter,
        exact=True,
    )
    return max(query.top_k, int(count.count))


def search_code_vector(
    client: Any,
    query: SearchQuery,
    query_vector: Sequence[float],
) -> Tuple[SearchResult, ...]:
    if client is None:
        raise ValueError("client must not be None")
    if not isinstance(query, SearchQuery):
        raise ValueError("query must be SearchQuery")

    values = tuple(float(item) for item in query_vector)
    if len(values) != CODE_EMBEDDING_DIMENSION:
        raise ValueError(
            "query_vector must match CODE_EMBEDDING_DIMENSION"
        )

    qdrant_filter = _build_vector_filter(query)
    limit = _search_limit(client, query, qdrant_filter)

    response = client.query_points(
        collection_name=CODE_VECTOR_COLLECTION,
        query=list(values),
        query_filter=qdrant_filter,
        limit=limit,
        with_payload=True,
        with_vectors=False,
    )

    results = []
    for point in response.points:
        payload = dict(point.payload or {})
        if not _path_matches(payload, query.path_filter):
            continue

        chunk_id = _payload_text(
            payload,
            "chunk_id",
            required=True,
        )
        document_id = _payload_text(
            payload,
            "document_id",
            required=True,
        )
        content = _payload_text(
            payload,
            "content",
            required=True,
        )
        source_type_raw = _payload_text(
            payload,
            "source_type",
            required=True,
        )
        assert chunk_id is not None
        assert document_id is not None
        assert content is not None
        assert source_type_raw is not None

        metadata = SourceMetadata(
            project_id=query.project_id,
            source_type=SourceType(source_type_raw),
            path=_payload_text(payload, "path"),
            symbol=_payload_text(payload, "symbol"),
            line_start=payload.get("line_start"),
            line_end=payload.get("line_end"),
            git_branch=_payload_text(payload, "git_branch"),
            git_commit=_payload_text(payload, "git_commit"),
            sha256=_payload_text(payload, "sha256"),
            indexed_at=_payload_text(payload, "indexed_at"),
            source_id=_payload_text(payload, "source_id"),
        )

        results.append(
            SearchResult(
                chunk_id=chunk_id,
                document_id=document_id,
                content=content,
                metadata=metadata,
                score=float(point.score),
                rank=len(results) + 1,
                retrieval_modes=(CODE_VECTOR_RETRIEVAL_MODE,),
                stale=False,
            )
        )
        if len(results) >= query.top_k:
            break

    return tuple(results)


def collect_code_hybrid_candidates(
    connection: sqlite3.Connection,
    vector_client: Any,
    query: SearchQuery,
    query_vector: Sequence[float],
) -> CodeHybridCandidates:
    if not isinstance(connection, sqlite3.Connection):
        raise ValueError("connection must be sqlite3.Connection")

    lexical = search_lexical_ranked(connection, query)
    vector = search_code_vector(
        vector_client,
        query,
        query_vector,
    )
    return CodeHybridCandidates(
        lexical=lexical,
        vector=vector,
    )
