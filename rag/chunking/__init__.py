"""Text and code chunking helpers for CodeBridge RAG."""

from .code_fallback import (
    CodeFallbackChunkDraft,
    FallbackReason,
    ParserMode,
    SafeCodeChunkingResult,
    safe_chunk_code,
)
from .code_lines import (
    CodeLineAccuracyError,
    CodeLineAccuracyReport,
    source_line_slice,
    validate_code_line_accuracy,
)
from .code_parser import (
    CodeLanguage,
    CodeParseError,
    CodeParseResult,
    ParserBackend,
    UnsupportedCodeLanguageError,
    detect_code_language,
    parse_code_source,
)
from .code_symbols import (
    CodeSymbol,
    CodeSymbolKind,
    extract_code_symbols,
)
from .code_units import (
    CodeUnitDraft,
    CodeUnitKind,
    chunk_code_units,
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
    "CodeFallbackChunkDraft",
    "FallbackReason",
    "ParserMode",
    "SafeCodeChunkingResult",
    "safe_chunk_code",
    "CodeLineAccuracyError",
    "CodeLineAccuracyReport",
    "source_line_slice",
    "validate_code_line_accuracy",
    "CodeLanguage",
    "CodeParseError",
    "CodeParseResult",
    "ParserBackend",
    "UnsupportedCodeLanguageError",
    "detect_code_language",
    "parse_code_source",
    "CodeSymbol",
    "CodeSymbolKind",
    "extract_code_symbols",
    "CodeUnitDraft",
    "CodeUnitKind",
    "chunk_code_units",
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
