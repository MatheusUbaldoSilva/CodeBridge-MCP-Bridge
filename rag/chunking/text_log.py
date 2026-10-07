"""Deterministic TXT and log chunking for RAG-003-B.

Semantic boundaries are preferred in this order:
1. section
2. execution
3. error
4. event
5. generic block

A controlled max_lines limit prevents unbounded chunks without introducing overlap.
No indexing, embeddings, model loading, filesystem I/O, or shell execution happens here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import List, Optional, Sequence, Tuple


class TextLogChunkKind(str, Enum):
    SECTION = "SECTION"
    EXECUTION = "EXECUTION"
    ERROR = "ERROR"
    EVENT = "EVENT"
    BLOCK = "BLOCK"


@dataclass(frozen=True)
class TextLogChunkDraft:
    ordinal: int
    content: str
    kind: TextLogChunkKind
    line_start: int
    line_end: int
    continuation: bool = False
    marker: Optional[str] = None

    def __post_init__(self) -> None:
        if self.ordinal < 0:
            raise ValueError("ordinal must be >= 0")
        if not isinstance(self.content, str) or not self.content.strip():
            raise ValueError("content must be a non-empty string")
        if not isinstance(self.kind, TextLogChunkKind):
            raise ValueError("kind must be TextLogChunkKind")
        if self.line_start < 1:
            raise ValueError("line_start must be >= 1")
        if self.line_end < self.line_start:
            raise ValueError("line_end must be >= line_start")
        if self.marker is not None and not str(self.marker).strip():
            raise ValueError("marker must be non-empty when provided")


_SECTION_RE = re.compile(
    r"^\s*(?:={3,}|-{3,})\s*(?P<title>[^=-].*?)\s*(?:={3,}|-{3,})\s*$"
    r"|^\s*\[SECTION\]\s*(?P<section>.+?)\s*$",
    re.IGNORECASE,
)
_EXECUTION_RE = re.compile(
    r"^\s*(?:\[EXECUTION\]\s*|execution(?:_id)?\s*[:=]\s*|execution\s+)"
    r"(?P<value>exec_[A-Za-z0-9_-]+|[A-Za-z0-9_.:-]+)",
    re.IGNORECASE,
)
_ERROR_RE = re.compile(
    r"^\s*(?:\[[^\]]+\]\s*)?"
    r"(?P<value>ERROR|FATAL|FAILED|FAILURE|TRACEBACK|EXCEPTION)\b",
    re.IGNORECASE,
)
_EVENT_LABEL_RE = re.compile(
    r"^\s*(?:\[EVENT\]\s*|EVENT\s*[:=]\s*)(?P<value>.+?)\s*$",
    re.IGNORECASE,
)
_EVENT_TIMESTAMP_RE = re.compile(
    r"^\s*(?:"
    r"\[\d{4}-\d{2}-\d{2}[T ][^\]]+\]"
    r"|\d{4}-\d{2}-\d{2}[T ][0-9:.]+(?:Z|[+-]\d{2}:?\d{2})?"
    r")\s*(?P<value>.*)$"
)


def _classify_marker(line: str) -> Tuple[Optional[TextLogChunkKind], Optional[str]]:
    section = _SECTION_RE.match(line)
    if section:
        marker = (section.group("title") or section.group("section") or "").strip()
        return TextLogChunkKind.SECTION, marker or None

    execution = _EXECUTION_RE.match(line)
    if execution:
        return TextLogChunkKind.EXECUTION, execution.group("value")

    error = _ERROR_RE.match(line)
    if error:
        return TextLogChunkKind.ERROR, error.group("value").upper()

    event = _EVENT_LABEL_RE.match(line)
    if event:
        return TextLogChunkKind.EVENT, event.group("value").strip()

    timestamp = _EVENT_TIMESTAMP_RE.match(line)
    if timestamp:
        marker = (timestamp.group("value") or "").strip()
        return TextLogChunkKind.EVENT, marker or None

    return None, None


def _trim_range(
    lines: Sequence[str],
    start: int,
    end: int,
) -> Optional[Tuple[int, int]]:
    while start <= end and not lines[start].strip():
        start += 1
    while end >= start and not lines[end].strip():
        end -= 1
    if start > end:
        return None
    return start, end


def chunk_text_log(
    text: str,
    *,
    max_lines: int = 80,
) -> Tuple[TextLogChunkDraft, ...]:
    """Split TXT/log content by semantic markers with a controlled line limit.

    Line numbers are 1-based parser coordinates.
    Overlap is intentionally zero in RAG-003-B.
    Full provenance is completed in RAG-003-D.
    """

    if not isinstance(text, str):
        raise ValueError("text must be a string")
    if not isinstance(max_lines, int) or isinstance(max_lines, bool) or max_lines < 1:
        raise ValueError("max_lines must be an integer >= 1")

    lines = text.splitlines()
    if not lines or not any(line.strip() for line in lines):
        return ()

    chunks: List[TextLogChunkDraft] = []
    start = 0
    current_kind = TextLogChunkKind.BLOCK
    current_marker: Optional[str] = None
    continuation = False

    def emit(
        raw_start: int,
        raw_end: int,
        kind: TextLogChunkKind,
        marker: Optional[str],
        is_continuation: bool,
    ) -> None:
        trimmed = _trim_range(lines, raw_start, raw_end)
        if trimmed is None:
            return
        line_start, line_end = trimmed
        chunks.append(
            TextLogChunkDraft(
                ordinal=len(chunks),
                content="\n".join(lines[line_start:line_end + 1]),
                kind=kind,
                line_start=line_start + 1,
                line_end=line_end + 1,
                continuation=is_continuation,
                marker=marker,
            )
        )

    index = 0
    while index < len(lines):
        marker_kind, marker_value = _classify_marker(lines[index])

        if (
            marker_kind is not None
            and index > start
            and any(line.strip() for line in lines[start:index])
        ):
            emit(
                start,
                index - 1,
                current_kind,
                current_marker,
                continuation,
            )
            start = index
            current_kind = marker_kind
            current_marker = marker_value
            continuation = False
        elif marker_kind is not None and (
            index == start
            or not any(line.strip() for line in lines[start:index])
        ):
            start = index
            current_kind = marker_kind
            current_marker = marker_value
            continuation = False

        if index - start + 1 >= max_lines:
            emit(
                start,
                index,
                current_kind,
                current_marker,
                continuation,
            )
            start = index + 1
            continuation = True

        index += 1

    if start < len(lines):
        emit(
            start,
            len(lines) - 1,
            current_kind,
            current_marker,
            continuation,
        )

    return tuple(chunks)
