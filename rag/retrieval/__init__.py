"""Retrieval helpers for CodeBridge RAG.

RAG-007-D adds only in-memory NL -> code proof retrieval.
No vector store is initialized here.
"""

from .code_semantic import retrieve_nl_to_code

__all__ = [
    "retrieve_nl_to_code",
]
