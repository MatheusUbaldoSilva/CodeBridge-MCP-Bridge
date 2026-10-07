"""Ranking helpers for CodeBridge RAG.

Importing this package has no model, database, network, or shell side effects.
"""

from .code_similarity import (
    rank_code_to_code,
    rank_nl_to_code,
)

__all__ = [
    "rank_code_to_code",
    "rank_nl_to_code",
]
