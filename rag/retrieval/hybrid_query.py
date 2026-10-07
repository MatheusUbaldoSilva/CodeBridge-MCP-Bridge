"""RAG-010-C — HYBRID query candidate collection across text and code.

This phase searches lexical FTS5 plus both persistent vector spaces when the
deterministic classifier selected QueryRoute.HYBRID.

Ranking fusion remains RAG-010-D and deduplication remains RAG-010-E.
"""

from __future__ import annotations

from dataclasses import dataclass
import sqlite3
from typing import Any, Sequence, Tuple

from rag.contracts import SearchQuery, SearchResult
from rag.index.lexical_ranking import search_lexical_ranked
from rag.runtime.query_classifier import QueryRoute

from .hybrid_code import search_code_vector
from .hybrid_text import search_text_vector


@dataclass(frozen=True)
class HybridQueryCandidates:
    lexical: Tuple[SearchResult, ...]
    text_vector: Tuple[SearchResult, ...]
    code_vector: Tuple[SearchResult, ...]
    route: QueryRoute = QueryRoute.HYBRID

    def __post_init__(self) -> None:
        if self.route is not QueryRoute.HYBRID:
            raise ValueError("HybridQueryCandidates requires HYBRID route")
        for field_name, values in (
            ("lexical", self.lexical),
            ("text_vector", self.text_vector),
            ("code_vector", self.code_vector),
        ):
            if any(not isinstance(item, SearchResult) for item in values):
                raise ValueError(
                    f"{field_name} must contain SearchResult values"
                )


def collect_hybrid_query_candidates(
    connection: sqlite3.Connection,
    vector_client: Any,
    query: SearchQuery,
    *,
    route: QueryRoute,
    text_query_vector: Sequence[float],
    code_query_vector: Sequence[float],
) -> HybridQueryCandidates:
    """Search FTS5, text vectors and code vectors for one HYBRID query.

    The three candidate lists remain independent by design.
    """

    if not isinstance(connection, sqlite3.Connection):
        raise ValueError("connection must be sqlite3.Connection")
    if not isinstance(query, SearchQuery):
        raise ValueError("query must be SearchQuery")
    if route is not QueryRoute.HYBRID:
        raise ValueError(
            "collect_hybrid_query_candidates requires QueryRoute.HYBRID"
        )

    lexical = search_lexical_ranked(connection, query)
    text_vector = search_text_vector(
        vector_client,
        query,
        text_query_vector,
    )
    code_vector = search_code_vector(
        vector_client,
        query,
        code_query_vector,
    )

    return HybridQueryCandidates(
        lexical=lexical,
        text_vector=text_vector,
        code_vector=code_vector,
        route=route,
    )
