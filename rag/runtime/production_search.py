"""Read-only semantic search adapter for persistent CodeBridge RAG indexes.

This module intentionally does not register itself or create a production index.
RAG-017-H must prove index consistency before enabling the adapter.
"""
from __future__ import annotations

from pathlib import Path
import sqlite3
import threading

from rag.contracts import SearchQuery, SearchResult
from rag.index.qdrant_local import (
    open_qdrant_local, close_qdrant_local, resolve_qdrant_local_path,
)
from rag.index.lexical_ranking import search_lexical_ranked
from rag.models.artifact_install import resolve_selected_model_path
from rag.models.code_artifact_install import resolve_selected_code_model_path
from rag.models.embedding import TextEmbeddingClient
from rag.models.code_embedding import CodeEmbeddingClient, CodeRetrievalTask
from rag.models.code_lifecycle import CodeModelLifecycle, build_code_server_config
from rag.models.lifecycle import LlamaServerConfig, TextModelLifecycle
from rag.ranking.rrf import reciprocal_rank_fusion
from rag.ranking.dedup import deduplicate_ranked_results
from rag.retrieval.hybrid_text import search_text_vector
from rag.retrieval.hybrid_code import search_code_vector
from rag.runtime.query_classifier import QueryRoute
from rag.runtime.status import build_rag_status, resolve_rag_sqlite_path

_MODEL_LOCK = threading.RLock()


class ProductionSearchUnavailable(RuntimeError):
    pass


def _embed_text(query: str, llama_server: Path):
    lifecycle = TextModelLifecycle(LlamaServerConfig(
        executable_path=llama_server,
        model_path=resolve_selected_model_path(),
        port=0, gpu_layers=99, device="CUDA0",
    ))
    lifecycle.load(timeout_seconds=90)
    try:
        return TextEmbeddingClient(lifecycle).embed_query(query).values
    finally:
        lifecycle.unload(timeout_seconds=15)


def _embed_code(query: str, llama_server: Path):
    lifecycle = CodeModelLifecycle(build_code_server_config(
        executable_path=llama_server,
        model_path=resolve_selected_code_model_path(),
        port=0, gpu_layers=99, device="CUDA0",
    ))
    lifecycle.load(timeout_seconds=90)
    try:
        return CodeEmbeddingClient(lifecycle).embed_query(
            CodeRetrievalTask.NL2CODE, query
        ).values
    finally:
        lifecycle.unload(timeout_seconds=15)


def search_persistent_semantic(
    query: SearchQuery,
    route: QueryRoute,
    *,
    llama_server: Path = Path(r"C:\llama\llama-server.exe"),
) -> tuple[SearchResult, ...]:
    """Search an already READY, persistent index; fail closed otherwise."""
    if not isinstance(query, SearchQuery) or not isinstance(route, QueryRoute):
        raise ValueError("SearchQuery and QueryRoute are required")
    if route is QueryRoute.LEXICAL_ONLY:
        raise ValueError("lexical-only must be handled by search_context")

    status = build_rag_status()
    index = status.index
    sqlite_path = resolve_rag_sqlite_path()
    qdrant_path = resolve_qdrant_local_path()
    if (
        index.get("state") != "READY"
        or not sqlite_path.is_file()
        or not qdrant_path.is_dir()
    ):
        raise ProductionSearchUnavailable("persistent RAG index is not READY")

    # Serialize model transitions. GPU memory must not carry both models.
    with _MODEL_LOCK:
        text_vector = None
        code_vector = None
        if route in (QueryRoute.TEXT, QueryRoute.HYBRID):
            text_vector = _embed_text(query.query, llama_server)
        if route in (QueryRoute.CODE, QueryRoute.HYBRID):
            code_vector = _embed_code(query.query, llama_server)

        connection = sqlite3.connect(
            f"{sqlite_path.resolve().as_uri()}?mode=ro", uri=True
        )
        vector_client = None
        try:
            vector_client = open_qdrant_local(qdrant_path)
            lexical = search_lexical_ranked(connection, query)
            rankings = [lexical]
            if text_vector is not None:
                rankings.append(search_text_vector(vector_client, query, text_vector))
            if code_vector is not None:
                rankings.append(search_code_vector(vector_client, query, code_vector))
            fused = reciprocal_rank_fusion(rankings, top_k=max(20,query.top_k*3))
            final = deduplicate_ranked_results(fused, top_k=query.top_k)
            return final.results
        finally:
            connection.close()
            if vector_client is not None:
                close_qdrant_local(vector_client)
