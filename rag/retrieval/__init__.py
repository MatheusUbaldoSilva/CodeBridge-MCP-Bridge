"""Retrieval helpers for CodeBridge RAG.

RAG-007-D/E keep their in-memory semantic proof retrieval.

RAG-010-A adds persistent text hybrid candidate collection but deliberately
does not fuse or deduplicate rankings here.
"""

from .code_semantic import (
    retrieve_code_to_code,
    retrieve_nl_to_code,
)
from .hybrid_code import (
    CODE_VECTOR_RETRIEVAL_MODE,
    CodeHybridCandidates,
    collect_code_hybrid_candidates,
    search_code_vector,
)
from .hybrid_text import (
    TEXT_VECTOR_RETRIEVAL_MODE,
    TextHybridCandidates,
    collect_text_hybrid_candidates,
    search_text_vector,
)

__all__ = [
    "retrieve_code_to_code",
    "retrieve_nl_to_code",
    "CODE_VECTOR_RETRIEVAL_MODE",
    "CodeHybridCandidates",
    "collect_code_hybrid_candidates",
    "search_code_vector",
    "TEXT_VECTOR_RETRIEVAL_MODE",
    "TextHybridCandidates",
    "collect_text_hybrid_candidates",
    "search_text_vector",
]
