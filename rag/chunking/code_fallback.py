"""Safe code chunking fallback for RAG-004-D.

Structural parsing is attempted first.
Only expected parser failures trigger textual fallback.
Unexpected internal errors are deliberately not swallowed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import PurePosixPath
from typing import List, Optional, Sequence, Tuple

from .code_parser import (
    CodeLanguage,
    CodeParseError,
    UnsupportedCodeLanguageError,
    detect_code_language,
)
from .code_symbols import CodeSymbol, extract_code_symbols
from .code_units import CodeUnitDraft, chunk_code_units


class ParserMode(str, Enum):
    STRUCTURAL = "STRUCTURAL"
    FALLBACK = "FALLBACK"


class FallbackReason(str, Enum):
    PARSE_ERROR = "PARSE_ERROR"
    UNSUPPORTED_LANGUAGE = "UNSUPPORTED_LANGUAGE"


@dataclass(frozen=True)
class CodeFallbackChunkDraft:
    ordinal: int
    content: str
    line_start: int
    line_end: int
    continuation: bool = False

    def __post_init__(self) -> None:
        if self.ordinal < 0:
            raise ValueError("ordinal must be >= 0")
        if not isinstance(self.content, str) or not self.content.strip():
            raise ValueError("content must be a non-empty string")
        if self.line_start < 1:
            raise ValueError("line_start must be >= 1")
        if self.line_end < self.line_start:
            raise ValueError("line_end must be >= line_start")


@dataclass(frozen=True)
class SafeCodeChunkingResult:
    parser_mode: ParserMode
    path: str
    language: Optional[CodeLanguage]
    structural_chunks: Tuple[CodeUnitDraft, ...] = ()
    fallback_chunks: Tuple[CodeFallbackChunkDraft, ...] = ()
    symbols: Tuple[CodeSymbol, ...] = ()
    fallback_reason: Optional[FallbackReason] = None
    parser_error_type: Optional[str] = None
    parser_error_message: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.parser_mode, ParserMode):
            raise ValueError("parser_mode must be ParserMode")
        if not isinstance(self.path, str) or not self.path.strip():
            raise ValueError("path must be non-empty")

        if self.parser_mode is ParserMode.STRUCTURAL:
            if self.fallback_chunks:
                raise ValueError(
                    "STRUCTURAL mode cannot contain fallback_chunks"
                )
            if self.fallback_reason is not None:
                raise ValueError(
                    "STRUCTURAL mode cannot contain fallback_reason"
                )
            if self.parser_error_type is not None:
                raise ValueError(
                    "STRUCTURAL mode cannot contain parser_error_type"
                )
            if self.parser_error_message is not None:
                raise ValueError(
                    "STRUCTURAL mode cannot contain parser_error_message"
                )
        else:
            if self.structural_chunks:
                raise ValueError(
                    "FALLBACK mode cannot contain structural_chunks"
                )
            if self.symbols:
                raise ValueError(
                    "FALLBACK mode cannot contain structural symbols"
                )
            if self.fallback_reason is None:
                raise ValueError(
                    "FALLBACK mode requires fallback_reason"
                )
            if not self.parser_error_type:
                raise ValueError(
                    "FALLBACK mode requires parser_error_type"
                )
            if not self.parser_error_message:
                raise ValueError(
                    "FALLBACK mode requires parser_error_message"
                )


def _normalize_path(path: str) -> str:
    value = str(path or "").strip().replace("\\", "/")
    if not value:
        raise ValueError("path must be a non-empty repository path")
    return str(PurePosixPath(value))


def _logical_ranges(lines: Sequence[str]) -> List[Tuple[int, int]]:
    ranges: List[Tuple[int, int]] = []
    index = 0

    while index < len(lines):
        while index < len(lines) and not lines[index].strip():
            index += 1

        if index >= len(lines):
            break

        start = index
        index += 1

        while index < len(lines) and lines[index].strip():
            index += 1

        ranges.append((start, index - 1))

    return ranges


def _fallback_text_chunks(
    text: str,
    *,
    max_lines: int,
) -> Tuple[CodeFallbackChunkDraft, ...]:
    if not isinstance(max_lines, int) or isinstance(max_lines, bool) or max_lines < 1:
        raise ValueError("max_lines must be an integer >= 1")

    lines = text.splitlines()
    if not lines or not any(line.strip() for line in lines):
        return ()

    chunks: List[CodeFallbackChunkDraft] = []

    for block_start, block_end in _logical_ranges(lines):
        part_start = block_start
        first_part = True

        while part_start <= block_end:
            part_end = min(
                block_end,
                part_start + max_lines - 1,
            )
            chunks.append(
                CodeFallbackChunkDraft(
                    ordinal=len(chunks),
                    content="\n".join(
                        lines[part_start:part_end + 1]
                    ),
                    line_start=part_start + 1,
                    line_end=part_end + 1,
                    continuation=not first_part,
                )
            )
            first_part = False
            part_start = part_end + 1

    return tuple(chunks)


def safe_chunk_code(
    text: str,
    *,
    path: str,
    fallback_max_lines: int = 80,
) -> SafeCodeChunkingResult:
    """Use structural chunking when possible and textual fallback otherwise."""

    if not isinstance(text, str):
        raise ValueError("text must be a string")

    normalized_path = _normalize_path(path)
    language = detect_code_language(normalized_path)

    try:
        structural_chunks = chunk_code_units(
            text,
            path=normalized_path,
        )
        symbols = extract_code_symbols(
            text,
            path=normalized_path,
        )
    except CodeParseError as exc:
        return SafeCodeChunkingResult(
            parser_mode=ParserMode.FALLBACK,
            path=normalized_path,
            language=language,
            fallback_chunks=_fallback_text_chunks(
                text,
                max_lines=fallback_max_lines,
            ),
            fallback_reason=FallbackReason.PARSE_ERROR,
            parser_error_type=type(exc).__name__,
            parser_error_message=str(exc),
        )
    except UnsupportedCodeLanguageError as exc:
        return SafeCodeChunkingResult(
            parser_mode=ParserMode.FALLBACK,
            path=normalized_path,
            language=language,
            fallback_chunks=_fallback_text_chunks(
                text,
                max_lines=fallback_max_lines,
            ),
            fallback_reason=FallbackReason.UNSUPPORTED_LANGUAGE,
            parser_error_type=type(exc).__name__,
            parser_error_message=str(exc),
        )

    return SafeCodeChunkingResult(
        parser_mode=ParserMode.STRUCTURAL,
        path=normalized_path,
        language=language,
        structural_chunks=structural_chunks,
        symbols=symbols,
    )
