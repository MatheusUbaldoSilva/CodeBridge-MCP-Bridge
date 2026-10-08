"""MCP-facing RAG search service for RAG-013-C.

Lexical search is always available when the SQLite index exists.
Semantic execution is optional and explicitly injectable. When it is not
registered the service degrades transparently to FTS5 and reports the fallback.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3
from typing import Callable, Iterable, Optional, Tuple

from rag.contracts import SearchQuery, SearchResult, SourceMetadata, SourceType
from rag.index.lexical_ranking import search_lexical_ranked
from rag.runtime.query_classifier import QueryRoute, classify_query
from rag.runtime.status import resolve_rag_sqlite_path


class RagSearchIndexUnavailableError(RuntimeError):
    pass


SemanticSearchExecutor = Callable[
    [SearchQuery, QueryRoute],
    Tuple[SearchResult, ...],
]


@dataclass(frozen=True)
class RagSearchContextResult:
    requested_route: QueryRoute
    effective_route: QueryRoute
    results: Tuple[SearchResult, ...]
    fallback_reason: Optional[str] = None

    def to_dict(self) -> dict[str, object]:
        return {
            "requested_route": self.requested_route.value,
            "effective_route": self.effective_route.value,
            "fallback_reason": self.fallback_reason,
            "result_count": len(self.results),
            "results": [
                search_result_to_dict(item)
                for item in self.results
            ],
        }


def source_metadata_to_dict(
    metadata: SourceMetadata,
) -> dict[str, object]:
    return {
        "project_id": metadata.project_id,
        "source_type": metadata.source_type.value,
        "path": metadata.path,
        "symbol": metadata.symbol,
        "line_start": metadata.line_start,
        "line_end": metadata.line_end,
        "git_branch": metadata.git_branch,
        "git_commit": metadata.git_commit,
        "git_provenance_commit": metadata.git_provenance_commit,
        "git_worktree_status": metadata.git_worktree_status,
        "sha256": metadata.sha256,
        "indexed_at": metadata.indexed_at,
        "source_id": metadata.source_id,
    }


def search_result_to_dict(
    result: SearchResult,
) -> dict[str, object]:
    return {
        "chunk_id": result.chunk_id,
        "document_id": result.document_id,
        "content": result.content,
        "metadata": source_metadata_to_dict(result.metadata),
        "score": float(result.score),
        "rank": int(result.rank),
        "retrieval_modes": list(result.retrieval_modes),
        "stale": bool(result.stale),
    }


def _parse_source_types(
    source_types: Iterable[str],
) -> Tuple[SourceType, ...]:
    parsed = []
    for raw in source_types:
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError(
                "source_types must contain non-empty SourceType names"
            )
        try:
            value = SourceType(raw.strip().upper())
        except ValueError as exc:
            raise ValueError(
                f"invalid source_type: {raw}"
            ) from exc
        if value not in parsed:
            parsed.append(value)
    return tuple(parsed)


def _connect_read_only(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise RagSearchIndexUnavailableError(
            f"RAG SQLite index is unavailable: {path}"
        )
    uri = f"{path.resolve().as_uri()}?mode=ro"
    try:
        return sqlite3.connect(uri, uri=True)
    except sqlite3.Error as exc:
        raise RagSearchIndexUnavailableError(
            f"failed to open RAG SQLite index read-only: {exc}"
        ) from exc


def search_context(
    *,
    query: str,
    project_id: str,
    source_types: Iterable[str] = (),
    top_k: int = 10,
    path_filter: Optional[str] = None,
    branch: Optional[str] = None,
    sqlite_path: Optional[str | Path] = None,
    semantic_executor: Optional[SemanticSearchExecutor] = None,
) -> RagSearchContextResult:
    parsed_source_types = _parse_source_types(source_types)
    search_query = SearchQuery(
        query=query,
        project_id=project_id,
        source_types=parsed_source_types,
        top_k=top_k,
        path_filter=path_filter,
        branch=branch,
    )

    classification = classify_query(
        query,
        source_types=parsed_source_types,
    )
    requested_route = classification.route

    if (
        requested_route is not QueryRoute.LEXICAL_ONLY
        and semantic_executor is not None
    ):
        semantic = semantic_executor(
            search_query,
            requested_route,
        )
        if any(not isinstance(item, SearchResult) for item in semantic):
            raise ValueError(
                "semantic_executor must return SearchResult values"
            )
        return RagSearchContextResult(
            requested_route=requested_route,
            effective_route=requested_route,
            results=tuple(semantic[:top_k]),
            fallback_reason=None,
        )

    selected_path = (
        Path(sqlite_path)
        if sqlite_path is not None
        else resolve_rag_sqlite_path()
    )

    connection = _connect_read_only(selected_path)
    try:
        lexical = search_lexical_ranked(
            connection,
            search_query,
        )
    except sqlite3.Error as exc:
        raise RagSearchIndexUnavailableError(
            f"RAG lexical index is unavailable: {exc}"
        ) from exc
    finally:
        connection.close()

    fallback_reason = None
    if requested_route is not QueryRoute.LEXICAL_ONLY:
        fallback_reason = "SEMANTIC_EXECUTOR_UNAVAILABLE"

    return RagSearchContextResult(
        requested_route=requested_route,
        effective_route=QueryRoute.LEXICAL_ONLY,
        results=tuple(lexical[:top_k]),
        fallback_reason=fallback_reason,
    )
