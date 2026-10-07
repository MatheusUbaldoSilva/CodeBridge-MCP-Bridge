"""Text and code chunking helpers for CodeBridge RAG."""

from .code_parser import (
    CodeLanguage,
    CodeParseError,
    CodeParseResult,
    ParserBackend,
    UnsupportedCodeLanguageError,
    detect_code_language,
    parse_code_source,
)
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
    "CodeLanguage",
    "CodeParseError",
    "CodeParseResult",
    "ParserBackend",
    "UnsupportedCodeLanguageError",
    "detect_code_language",
    "parse_code_source",
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
