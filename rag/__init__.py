"""CodeBridge 2.0 local RAG layer.

Importing this package must stay side-effect free.
"""

from .contracts import (
    Chunk,
    Document,
    IndexState,
    ModelState,
    SearchQuery,
    SearchResult,
    SourceMetadata,
    SourceType,
)

__all__ = [
    "Chunk",
    "Document",
    "IndexState",
    "ModelState",
    "SearchQuery",
    "SearchResult",
    "SourceMetadata",
    "SourceType",
]
