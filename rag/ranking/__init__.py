"""Ranking helpers for CodeBridge RAG.

Importing this package has no model, database, network, or shell side effects.
"""

from .code_similarity import (
    rank_code_to_code,
    rank_nl_to_code,
)
from .dedup import (
    NEAR_DUPLICATE_JACCARD_THRESHOLD,
    DeduplicationOutcome,
    SuppressedDuplicate,
    deduplicate_ranked_results,
)
from .rrf import (
    DEFAULT_RRF_K,
    reciprocal_rank_fusion,
)

__all__ = [
    "rank_code_to_code",
    "rank_nl_to_code",
    "NEAR_DUPLICATE_JACCARD_THRESHOLD",
    "DeduplicationOutcome",
    "SuppressedDuplicate",
    "deduplicate_ranked_results",
    "DEFAULT_RRF_K",
    "reciprocal_rank_fusion",
]
