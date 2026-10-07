"""Deterministic near-duplicate suppression for RAG-010-E."""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from typing import Iterable, Tuple

from rag.contracts import SearchResult


NEAR_DUPLICATE_JACCARD_THRESHOLD = 0.90
NEAR_DUPLICATE_MIN_TOKENS = 12
NEAR_DUPLICATE_SHINGLE_SIZE = 5

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


@dataclass(frozen=True)
class SuppressedDuplicate:
    suppressed_chunk_id: str
    kept_chunk_id: str
    similarity: float
    reason: str

    def __post_init__(self) -> None:
        if not self.suppressed_chunk_id:
            raise ValueError("suppressed_chunk_id must be non-empty")
        if not self.kept_chunk_id:
            raise ValueError("kept_chunk_id must be non-empty")
        if not 0.0 <= float(self.similarity) <= 1.0:
            raise ValueError("similarity must be between 0 and 1")
        if self.reason not in {"NORMALIZED_EXACT", "TOKEN_SHINGLE_JACCARD"}:
            raise ValueError("unsupported duplicate reason")


@dataclass(frozen=True)
class DeduplicationOutcome:
    results: Tuple[SearchResult, ...]
    suppressed: Tuple[SuppressedDuplicate, ...]

    def __post_init__(self) -> None:
        if any(not isinstance(item, SearchResult) for item in self.results):
            raise ValueError("results must contain SearchResult values")
        if any(
            not isinstance(item, SuppressedDuplicate)
            for item in self.suppressed
        ):
            raise ValueError(
                "suppressed must contain SuppressedDuplicate values"
            )


def _normalized_tokens(content: str) -> tuple[str, ...]:
    normalized = unicodedata.normalize("NFKC", content).casefold()
    return tuple(_TOKEN_RE.findall(normalized))


def _exact_signature(tokens: Iterable[str]) -> str:
    return " ".join(tokens)


def _token_shingles(
    tokens: tuple[str, ...],
    size: int,
) -> frozenset[tuple[str, ...]]:
    if len(tokens) < size:
        return frozenset()
    return frozenset(
        tuple(tokens[index:index + size])
        for index in range(0, len(tokens) - size + 1)
    )


def _jaccard(
    left: frozenset[tuple[str, ...]],
    right: frozenset[tuple[str, ...]],
) -> float:
    if not left or not right:
        return 0.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def deduplicate_ranked_results(
    results: Iterable[SearchResult],
    *,
    threshold: float = NEAR_DUPLICATE_JACCARD_THRESHOLD,
    min_tokens: int = NEAR_DUPLICATE_MIN_TOKENS,
    shingle_size: int = NEAR_DUPLICATE_SHINGLE_SIZE,
    top_k: int | None = None,
) -> DeduplicationOutcome:
    """Suppress near-identical chunks while preserving ranking order.

    The first and therefore highest-ranked representative wins.
    """

    numeric_threshold = float(threshold)
    if not 0.0 <= numeric_threshold <= 1.0:
        raise ValueError("threshold must be between 0 and 1")
    if not isinstance(min_tokens, int) or min_tokens < 1:
        raise ValueError("min_tokens must be an integer >= 1")
    if not isinstance(shingle_size, int) or shingle_size < 1:
        raise ValueError("shingle_size must be an integer >= 1")
    if top_k is not None and (
        not isinstance(top_k, int) or top_k < 1
    ):
        raise ValueError("top_k must be an integer >= 1 when provided")

    kept: list[
        tuple[
            SearchResult,
            tuple[str, ...],
            str,
            frozenset[tuple[str, ...]],
        ]
    ] = []
    suppressed: list[SuppressedDuplicate] = []

    for item in results:
        if not isinstance(item, SearchResult):
            raise ValueError("results must contain SearchResult values")

        tokens = _normalized_tokens(item.content)
        signature = _exact_signature(tokens)
        shingles = _token_shingles(tokens, shingle_size)

        duplicate: SuppressedDuplicate | None = None

        for kept_item, kept_tokens, kept_signature, kept_shingles in kept:
            if signature == kept_signature:
                duplicate = SuppressedDuplicate(
                    suppressed_chunk_id=item.chunk_id,
                    kept_chunk_id=kept_item.chunk_id,
                    similarity=1.0,
                    reason="NORMALIZED_EXACT",
                )
                break

            if (
                len(tokens) >= min_tokens
                and len(kept_tokens) >= min_tokens
            ):
                similarity = _jaccard(shingles, kept_shingles)
                if similarity >= numeric_threshold:
                    duplicate = SuppressedDuplicate(
                        suppressed_chunk_id=item.chunk_id,
                        kept_chunk_id=kept_item.chunk_id,
                        similarity=similarity,
                        reason="TOKEN_SHINGLE_JACCARD",
                    )
                    break

        if duplicate is not None:
            suppressed.append(duplicate)
            continue

        kept.append(
            (
                item,
                tokens,
                signature,
                shingles,
            )
        )

    if top_k is not None:
        kept = kept[:top_k]

    reranked = tuple(
        SearchResult(
            chunk_id=item.chunk_id,
            document_id=item.document_id,
            content=item.content,
            metadata=item.metadata,
            score=item.score,
            rank=rank,
            retrieval_modes=item.retrieval_modes,
            stale=item.stale,
        )
        for rank, (item, _, _, _) in enumerate(kept, 1)
    )

    return DeduplicationOutcome(
        results=reranked,
        suppressed=tuple(suppressed),
    )
