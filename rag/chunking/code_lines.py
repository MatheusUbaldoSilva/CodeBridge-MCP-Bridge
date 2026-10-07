"""Exact source-line validation for RAG-004-E."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Tuple

from .code_fallback import ParserMode, SafeCodeChunkingResult
from .code_symbols import CodeSymbolKind


class CodeLineAccuracyError(ValueError):
    pass


@dataclass(frozen=True)
class CodeLineAccuracyReport:
    parser_mode: ParserMode
    source_line_count: int
    chunk_count: int
    symbol_count: int

    def __post_init__(self) -> None:
        if self.source_line_count < 0:
            raise ValueError("source_line_count must be >= 0")
        if self.chunk_count < 0:
            raise ValueError("chunk_count must be >= 0")
        if self.symbol_count < 0:
            raise ValueError("symbol_count must be >= 0")


def source_line_slice(
    text: str,
    *,
    line_start: int,
    line_end: int,
) -> str:
    """Return the exact logical-line slice addressed by 1-based coordinates."""

    if not isinstance(text, str):
        raise ValueError("text must be a string")
    if not isinstance(line_start, int) or isinstance(line_start, bool):
        raise ValueError("line_start must be an integer")
    if not isinstance(line_end, int) or isinstance(line_end, bool):
        raise ValueError("line_end must be an integer")
    if line_start < 1:
        raise ValueError("line_start must be >= 1")
    if line_end < line_start:
        raise ValueError("line_end must be >= line_start")

    lines = text.splitlines()
    if line_end > len(lines):
        raise ValueError("line range exceeds source line count")

    return "\n".join(lines[line_start - 1:line_end])


def _validate_chunk(
    text: str,
    chunk: Any,
    *,
    source_line_count: int,
) -> None:
    if chunk.line_start < 1:
        raise CodeLineAccuracyError(
            f"chunk {chunk.ordinal} line_start must be >= 1"
        )
    if chunk.line_end < chunk.line_start:
        raise CodeLineAccuracyError(
            f"chunk {chunk.ordinal} line_end precedes line_start"
        )
    if chunk.line_end > source_line_count:
        raise CodeLineAccuracyError(
            f"chunk {chunk.ordinal} exceeds source line count"
        )

    expected = source_line_slice(
        text,
        line_start=chunk.line_start,
        line_end=chunk.line_end,
    )
    if chunk.content != expected:
        raise CodeLineAccuracyError(
            f"chunk {chunk.ordinal} content does not match "
            f"source lines {chunk.line_start}-{chunk.line_end}"
        )


def _validate_symbols(
    text: str,
    symbols: Tuple[Any, ...],
    *,
    source_line_count: int,
) -> None:
    for symbol in symbols:
        if symbol.kind is CodeSymbolKind.MODULE:
            expected_end = max(1, source_line_count)
            if symbol.line_start != 1 or symbol.line_end != expected_end:
                raise CodeLineAccuracyError(
                    "MODULE symbol must span the logical source range"
                )
            continue

        if source_line_count == 0:
            raise CodeLineAccuracyError(
                "non-MODULE symbol cannot exist in an empty source"
            )
        if symbol.line_start < 1:
            raise CodeLineAccuracyError(
                f"symbol {symbol.qualified_name} line_start must be >= 1"
            )
        if symbol.line_end < symbol.line_start:
            raise CodeLineAccuracyError(
                f"symbol {symbol.qualified_name} has inverted line range"
            )
        if symbol.line_end > source_line_count:
            raise CodeLineAccuracyError(
                f"symbol {symbol.qualified_name} exceeds source line count"
            )

        symbol_slice = source_line_slice(
            text,
            line_start=symbol.line_start,
            line_end=symbol.line_end,
        )
        anchor = symbol.name.lstrip("~")
        if anchor and anchor not in symbol_slice:
            raise CodeLineAccuracyError(
                f"symbol {symbol.qualified_name} is not anchored "
                "inside its declared source range"
            )


def validate_code_line_accuracy(
    text: str,
    result: SafeCodeChunkingResult,
) -> CodeLineAccuracyReport:
    """Validate exact line coordinates for structural/fallback code results."""

    if not isinstance(text, str):
        raise ValueError("text must be a string")
    if not isinstance(result, SafeCodeChunkingResult):
        raise ValueError("result must be SafeCodeChunkingResult")

    source_line_count = len(text.splitlines())

    if result.parser_mode is ParserMode.STRUCTURAL:
        chunks = result.structural_chunks
        symbols = result.symbols
    else:
        chunks = result.fallback_chunks
        symbols = ()

    if source_line_count == 0 and chunks:
        raise CodeLineAccuracyError(
            "empty source cannot contain chunks"
        )

    for chunk in chunks:
        _validate_chunk(
            text,
            chunk,
            source_line_count=source_line_count,
        )

    _validate_symbols(
        text,
        tuple(symbols),
        source_line_count=source_line_count,
    )

    return CodeLineAccuracyReport(
        parser_mode=result.parser_mode,
        source_line_count=source_line_count,
        chunk_count=len(chunks),
        symbol_count=len(symbols),
    )
