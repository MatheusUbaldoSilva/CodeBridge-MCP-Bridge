"""Deterministic cosine ranking for code semantic candidates — RAG-007-D/E."""

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


CODE_VECTOR_RETRIEVAL_MODE = "CODE_VECTOR_IN_MEMORY"
# Backward-compatible public name frozen by RAG-007-D.
CODE_NL_RETRIEVAL_MODE = CODE_VECTOR_RETRIEVAL_MODE
CODE_NL_TASK_MODE = "NL2CODE"
CODE_CODE_TASK_MODE = "CODE2CODE"


def _rank_code_task(
    query_embedding: CodeEmbeddingVector,
    chunks: Sequence[Chunk],
    chunk_embeddings: Sequence[CodeChunkEmbedding],
    *,
    task: CodeRetrievalTask,
    task_mode: str,
    top_k: int,
) -> Tuple[SearchResult, ...]:
    if not isinstance(query_embedding, CodeEmbeddingVector):
        raise ValueError("query_embedding must be CodeEmbeddingVector")
    if not isinstance(task, CodeRetrievalTask):
        raise ValueError("task must be CodeRetrievalTask")
    if (
        query_embedding.task is not task
        or query_embedding.role is not CodeEmbeddingRole.QUERY
    ):
        raise ValueError(
            f"{task.value} ranking requires a matching QUERY embedding"
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
            raise ValueError("code semantic ranking accepts only SourceType.CODE")
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
        if embedded.task is not task:
            raise ValueError("candidate embedding task does not match query task")
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

    return tuple(
        SearchResult(
            chunk_id=item[4].chunk_id,
            document_id=item[4].document_id,
            content=item[4].content,
            metadata=item[4].metadata,
            score=item[5],
            rank=rank,
            retrieval_modes=(
                CODE_VECTOR_RETRIEVAL_MODE,
                task_mode,
            ),
            stale=False,
        )
        for rank, item in enumerate(scored[:top_k], start=1)
    )


def rank_nl_to_code(
    query_embedding: CodeEmbeddingVector,
    chunks: Sequence[Chunk],
    chunk_embeddings: Sequence[CodeChunkEmbedding],
    *,
    top_k: int,
) -> Tuple[SearchResult, ...]:
    return _rank_code_task(
        query_embedding,
        chunks,
        chunk_embeddings,
        task=CodeRetrievalTask.NL2CODE,
        task_mode=CODE_NL_TASK_MODE,
        top_k=top_k,
    )


def rank_code_to_code(
    query_embedding: CodeEmbeddingVector,
    chunks: Sequence[Chunk],
    chunk_embeddings: Sequence[CodeChunkEmbedding],
    *,
    top_k: int,
) -> Tuple[SearchResult, ...]:
    return _rank_code_task(
        query_embedding,
        chunks,
        chunk_embeddings,
        task=CodeRetrievalTask.CODE2CODE,
        task_mode=CODE_CODE_TASK_MODE,
        top_k=top_k,
    )
