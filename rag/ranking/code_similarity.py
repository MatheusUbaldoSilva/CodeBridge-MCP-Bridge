"""Deterministic cosine ranking for NL -> code candidates — RAG-007-D."""

from __future__ import annotations

import math
from typing import Sequence, Tuple

from rag.contracts import Chunk, SearchResult, SourceType
from rag.models.code_backend_policy import CodeRetrievalTask
from rag.models.code_embedding import (
    CodeChunkEmbedding,
    CodeEmbeddingRole,
    CodeEmbeddingVector,
)
from rag.models.embedding import cosine_similarity


CODE_NL_RETRIEVAL_MODE = "CODE_VECTOR_IN_MEMORY"
CODE_NL_TASK_MODE = "NL2CODE"


def rank_nl_to_code(
    query_embedding: CodeEmbeddingVector,
    chunks: Sequence[Chunk],
    chunk_embeddings: Sequence[CodeChunkEmbedding],
    *,
    top_k: int,
) -> Tuple[SearchResult, ...]:
    if not isinstance(query_embedding, CodeEmbeddingVector):
        raise ValueError("query_embedding must be CodeEmbeddingVector")
    if (
        query_embedding.task is not CodeRetrievalTask.NL2CODE
        or query_embedding.role is not CodeEmbeddingRole.QUERY
    ):
        raise ValueError(
            "NL -> code ranking requires an NL2CODE QUERY embedding"
        )
    if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k < 1:
        raise ValueError("top_k must be >= 1")
    if len(chunks) != len(chunk_embeddings):
        raise ValueError("chunks and chunk_embeddings must have equal length")

    seen_ids = set()
    scored = []

    for chunk, embedded in zip(chunks, chunk_embeddings):
        if not isinstance(chunk, Chunk):
            raise ValueError("chunks must contain only Chunk values")
        if chunk.metadata.source_type is not SourceType.CODE:
            raise ValueError("NL -> code ranking accepts only SourceType.CODE")
        if chunk.chunk_id in seen_ids:
            raise ValueError("chunk_id values must be unique")
        seen_ids.add(chunk.chunk_id)

        if not isinstance(embedded, CodeChunkEmbedding):
            raise ValueError(
                "chunk_embeddings must contain only CodeChunkEmbedding values"
            )
        if embedded.chunk_id != chunk.chunk_id:
            raise ValueError("chunk embedding identity does not match chunk")
        if embedded.document_id != chunk.document_id:
            raise ValueError("document identity does not match chunk")
        if embedded.metadata != chunk.metadata:
            raise ValueError("chunk embedding provenance does not match chunk")
        if embedded.task is not CodeRetrievalTask.NL2CODE:
            raise ValueError("candidate embedding must use NL2CODE task")
        if embedded.embedding.role is not CodeEmbeddingRole.PASSAGE:
            raise ValueError("candidate embedding must use PASSAGE role")

        score = float(
            cosine_similarity(
                query_embedding.values,
                embedded.embedding.values,
            )
        )
        if not math.isfinite(score):
            raise ValueError("cosine score must be finite")

        path = chunk.metadata.path or ""
        line_start = chunk.metadata.line_start or 0
        scored.append(
            (
                -score,
                path,
                line_start,
                chunk.chunk_id,
                chunk,
                score,
            )
        )

    scored.sort(
        key=lambda item: (
            item[0],
            item[1],
            item[2],
            item[3],
        )
    )

    results = []
    for rank, item in enumerate(scored[:top_k], start=1):
        chunk = item[4]
        score = item[5]
        results.append(
            SearchResult(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                content=chunk.content,
                metadata=chunk.metadata,
                score=score,
                rank=rank,
                retrieval_modes=(
                    CODE_NL_RETRIEVAL_MODE,
                    CODE_NL_TASK_MODE,
                ),
                stale=False,
            )
        )

    return tuple(results)
