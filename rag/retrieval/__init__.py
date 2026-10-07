"""Retrieval helpers for CodeBridge RAG.

RAG-007-D/E add only in-memory semantic proof retrieval.
No vector store is initialized here.
"""

from .code_semantic import (
    retrieve_code_to_code,
    retrieve_nl_to_code,
)

__all__ = [
    "retrieve_code_to_code",
    "retrieve_nl_to_code",
]
