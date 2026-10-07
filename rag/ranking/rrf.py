"""Deterministic Reciprocal Rank Fusion for RAG-010-D."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Sequence, Tuple

from rag.contracts import SearchResult


DEFAULT_RRF_K = 60


@dataclass
class _RrfAccumulator:
    canonical: SearchResult
    score: float = 0.0
    best_rank: int = 2**31 - 1
    retrieval_modes: tuple[str, ...] = ()


def _merge_modes(
    current: tuple[str, ...],
    incoming: Iterable[str],
) -> tuple[str, ...]:
    seen = set(current)
    merged = list(current)
    for mode in incoming:
        if mode not in seen:
            seen.add(mode)
            merged.append(mode)
    return tuple(merged)


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[SearchResult]],
    *,
    k: int = DEFAULT_RRF_K,
    top_k: int | None = None,
) -> Tuple[SearchResult, ...]:
    """Fuse ranked lists using deterministic RRF.

    Exact chunk_id matches are the identity used for cross-list score
    aggregation. Near-duplicate content is intentionally not collapsed here;
    RAG-010-E owns that policy.
    """

    if not isinstance(k, int) or k < 1:
        raise ValueError("k must be an integer >= 1")
    if top_k is not None and (
        not isinstance(top_k, int) or top_k < 1
    ):
        raise ValueError("top_k must be an integer >= 1 when provided")

    accumulators: Dict[str, _RrfAccumulator] = {}

    for ranking in rankings:
        seen_in_ranking: set[str] = set()

        for position, result in enumerate(ranking, 1):
            if not isinstance(result, SearchResult):
                raise ValueError(
                    "rankings must contain only SearchResult values"
                )
            if result.chunk_id in seen_in_ranking:
                continue
            seen_in_ranking.add(result.chunk_id)

            accumulator = accumulators.get(result.chunk_id)

            if accumulator is None:
                accumulator = _RrfAccumulator(canonical=result)
                accumulators[result.chunk_id] = accumulator
            else:
                canonical = accumulator.canonical
                if canonical.document_id != result.document_id:
                    raise ValueError(
                        f"chunk_id {result.chunk_id} has conflicting document_id"
                    )
                if canonical.content != result.content:
                    raise ValueError(
                        f"chunk_id {result.chunk_id} has conflicting content"
                    )
                if canonical.metadata != result.metadata:
                    raise ValueError(
                        f"chunk_id {result.chunk_id} has conflicting metadata"
                    )

            accumulator.score += 1.0 / (k + position)
            accumulator.best_rank = min(
                accumulator.best_rank,
                position,
            )
            accumulator.retrieval_modes = _merge_modes(
                accumulator.retrieval_modes,
                result.retrieval_modes,
            )

    ordered = sorted(
        accumulators.values(),
        key=lambda item: (
            -item.score,
            item.best_rank,
            item.canonical.chunk_id,
        ),
    )

    if top_k is not None:
        ordered = ordered[:top_k]

    fused = []
    for rank, item in enumerate(ordered, 1):
        source = item.canonical
        fused.append(
            SearchResult(
                chunk_id=source.chunk_id,
                document_id=source.document_id,
                content=source.content,
                metadata=source.metadata,
                score=item.score,
                rank=rank,
                retrieval_modes=item.retrieval_modes,
                stale=source.stale,
            )
        )

    return tuple(fused)
