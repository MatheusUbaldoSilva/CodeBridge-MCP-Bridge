"""In-memory code semantic retrieval proof — RAG-007-D/E.

These helpers deliberately recompute passage embeddings from supplied code chunks.
They do not persist vectors or create a production vector index.
"""

from __future__ import annotations

from typing import Iterable, Protocol, Tuple

from rag.contracts import Chunk, SearchResult, SourceType
from rag.models.code_backend_policy import CodeRetrievalTask
from rag.models.code_embedding import (
    CodeChunkEmbedding,
    CodeEmbeddingVector,
)
from rag.ranking.code_similarity import (
    rank_code_to_code,
    rank_nl_to_code,
)


class CodeSemanticRetrievalClient(Protocol):
    def embed_query(
        self,
        task: CodeRetrievalTask,
        text: str,
    ) -> CodeEmbeddingVector:
        ...

    def embed_code_chunks(
        self,
        chunks: Iterable[Chunk],
        *,
        task: CodeRetrievalTask = CodeRetrievalTask.NL2CODE,
    ) -> Tuple[CodeChunkEmbedding, ...]:
        ...


def _validated_chunks(
    chunks: Iterable[Chunk],
) -> Tuple[Chunk, ...]:
    items = tuple(chunks)
    if any(not isinstance(chunk, Chunk) for chunk in items):
        raise ValueError("chunks must contain only Chunk values")
    if any(
        chunk.metadata.source_type is not SourceType.CODE
        for chunk in items
    ):
        raise ValueError("code semantic retrieval accepts only SourceType.CODE")
    return items


def _validate_query_and_top_k(query: str, top_k: int) -> None:
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string")
    if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k < 1:
        raise ValueError("top_k must be >= 1")


def _validate_client(client: CodeSemanticRetrievalClient) -> None:
    if not hasattr(client, "embed_query") or not hasattr(
        client,
        "embed_code_chunks",
    ):
        raise ValueError(
            "client must provide embed_query and embed_code_chunks"
        )


def retrieve_nl_to_code(
    client: CodeSemanticRetrievalClient,
    query: str,
    chunks: Iterable[Chunk],
    *,
    top_k: int = 5,
) -> Tuple[SearchResult, ...]:
    _validate_query_and_top_k(query, top_k)
    _validate_client(client)
    items = _validated_chunks(chunks)
    if not items:
        return ()

    query_embedding = client.embed_query(
        CodeRetrievalTask.NL2CODE,
        query,
    )
    chunk_embeddings = client.embed_code_chunks(
        items,
        task=CodeRetrievalTask.NL2CODE,
    )
    return rank_nl_to_code(
        query_embedding,
        items,
        chunk_embeddings,
        top_k=top_k,
    )


def retrieve_code_to_code(
    client: CodeSemanticRetrievalClient,
    query_code: str,
    chunks: Iterable[Chunk],
    *,
    top_k: int = 5,
) -> Tuple[SearchResult, ...]:
    _validate_query_and_top_k(query_code, top_k)
    _validate_client(client)
    items = _validated_chunks(chunks)
    if not items:
        return ()

    query_embedding = client.embed_query(
        CodeRetrievalTask.CODE2CODE,
        query_code,
    )
    chunk_embeddings = client.embed_code_chunks(
        items,
        task=CodeRetrievalTask.CODE2CODE,
    )
    return rank_code_to_code(
        query_embedding,
        items,
        chunk_embeddings,
        top_k=top_k,
    )
