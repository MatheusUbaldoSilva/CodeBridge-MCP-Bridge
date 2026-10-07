"""In-memory NL -> code retrieval proof — RAG-007-D.

This module deliberately recomputes passage embeddings from supplied code chunks.
It does not persist vectors or create a production vector index.
"""

from __future__ import annotations

from typing import Iterable, Protocol, Tuple

from rag.contracts import Chunk, SearchResult, SourceType
from rag.models.code_backend_policy import CodeRetrievalTask
from rag.models.code_embedding import (
    CodeChunkEmbedding,
    CodeEmbeddingVector,
)
from rag.ranking.code_similarity import rank_nl_to_code


class CodeNlRetrievalClient(Protocol):
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


def retrieve_nl_to_code(
    client: CodeNlRetrievalClient,
    query: str,
    chunks: Iterable[Chunk],
    *,
    top_k: int = 5,
) -> Tuple[SearchResult, ...]:
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string")
    if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k < 1:
        raise ValueError("top_k must be >= 1")
    if not hasattr(client, "embed_query") or not hasattr(
        client,
        "embed_code_chunks",
    ):
        raise ValueError(
            "client must provide embed_query and embed_code_chunks"
        )

    items = tuple(chunks)
    if any(not isinstance(chunk, Chunk) for chunk in items):
        raise ValueError("chunks must contain only Chunk values")
    if any(
        chunk.metadata.source_type is not SourceType.CODE
        for chunk in items
    ):
        raise ValueError("NL -> code retrieval accepts only SourceType.CODE")
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
