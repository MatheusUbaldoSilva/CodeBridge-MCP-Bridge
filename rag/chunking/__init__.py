"""Text chunking helpers for CodeBridge RAG."""

from .markdown import (
    MarkdownChunkDraft,
    MarkdownChunkKind,
    chunk_markdown,
)
from .overlap import (
    ControlledOverlapChunk,
    OverlapReason,
    apply_controlled_overlap,
)
from .provenance import (
    attach_source_provenance,
    source_sha256,
)
from .text_log import (
    TextLogChunkDraft,
    TextLogChunkKind,
    chunk_text_log,
)

__all__ = [
    "MarkdownChunkDraft",
    "MarkdownChunkKind",
    "chunk_markdown",
    "ControlledOverlapChunk",
    "OverlapReason",
    "apply_controlled_overlap",
    "attach_source_provenance",
    "source_sha256",
    "TextLogChunkDraft",
    "TextLogChunkKind",
    "chunk_text_log",
]
