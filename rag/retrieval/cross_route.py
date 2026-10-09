"""Opt-in cross-route semantic retrieval for code and prose evidence.

Requires query embeddings already produced by authorized local model clients.
No model lifecycle or production activation here.
"""
from __future__ import annotations
import sqlite3
from typing import Any, Sequence
from rag.contracts import SearchQuery,SearchResult
from rag.retrieval.hybrid_code import search_code_vector
from rag.ranking.semantic_document_reranker import rerank_documents

def cross_route_document_rank(
    connection:sqlite3.Connection, vector_client:Any,
    query:SearchQuery, rankings:Sequence[Sequence[SearchResult]],
    code_query_vector:Sequence[float],
    *,top_k:int=10,rrf_k:int=10,
)->tuple[SearchResult,...]:
    """Append scoped CODE semantic candidates even on initially TEXT queries."""
    if not isinstance(query,SearchQuery):
        raise ValueError("SearchQuery required")
    if not isinstance(connection,sqlite3.Connection):
        raise ValueError("SQLite connection required")
    for ranking in rankings:
        for item in ranking:
            if item.metadata.project_id!=query.project_id:
                raise ValueError("candidate project mismatch")
    extra=search_code_vector(vector_client,query,code_query_vector)
    if any(item.metadata.project_id!=query.project_id for item in extra):
        raise ValueError("vector candidate project mismatch")
    return rerank_documents((*rankings,extra),rrf_k=rrf_k,top_k=top_k)
