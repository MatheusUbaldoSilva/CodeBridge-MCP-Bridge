"""Controlled overlap policy for RAG-003-C.

Overlap is a post-chunking view and never changes the source chunks.

Default policy:
- only chunks explicitly marked continuation=True are eligible
- previous and current chunks must be line-contiguous
- semantic kind and marker must remain compatible when present
- overlap is capped by requested lines, a hard line cap, and a fraction of
  the current primary chunk size
- Markdown chunks do not receive overlap by default because they do not
  represent forced continuation splits

No filesystem I/O, indexing, embeddings, model loading, or shell execution
happens here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Any, Optional, Sequence, Tuple


class OverlapReason(str, Enum):
    FORCED_CONTINUATION = "FORCED_CONTINUATION"


@dataclass(frozen=True)
class ControlledOverlapChunk:
    source_ordinal: int
    content: str
    primary_content: str
    primary_line_start: int
    primary_line_end: int
    overlap_line_start: Optional[int] = None
    overlap_line_end: Optional[int] = None
    overlap_lines: int = 0
    reason: Optional[OverlapReason] = None

    def __post_init__(self) -> None:
        if self.source_ordinal < 0:
            raise ValueError("source_ordinal must be >= 0")
        if not isinstance(self.content, str) or not self.content.strip():
            raise ValueError("content must be a non-empty string")
        if not isinstance(self.primary_content, str) or not self.primary_content.strip():
            raise ValueError("primary_content must be a non-empty string")
        if self.primary_line_start < 1:
            raise ValueError("primary_line_start must be >= 1")
        if self.primary_line_end < self.primary_line_start:
            raise ValueError("primary_line_end must be >= primary_line_start")
        if self.overlap_lines < 0:
            raise ValueError("overlap_lines must be >= 0")

        has_overlap_range = (
            self.overlap_line_start is not None
            or self.overlap_line_end is not None
        )
        if self.overlap_lines == 0:
            if has_overlap_range or self.reason is not None:
                raise ValueError("zero-overlap chunks cannot have overlap range or reason")
        else:
            if self.overlap_line_start is None or self.overlap_line_end is None:
                raise ValueError("overlap range is required when overlap_lines > 0")
            if self.overlap_line_start < 1:
                raise ValueError("overlap_line_start must be >= 1")
            if self.overlap_line_end < self.overlap_line_start:
                raise ValueError("overlap_line_end must be >= overlap_line_start")
            if (
                self.overlap_line_end - self.overlap_line_start + 1
                != self.overlap_lines
            ):
                raise ValueError("overlap range must match overlap_lines")
            if not isinstance(self.reason, OverlapReason):
                raise ValueError("reason must be OverlapReason when overlap is applied")

    @property
    def overlap_applied(self) -> bool:
        return self.overlap_lines > 0


def _validate_policy(
    overlap_lines: int,
    max_overlap_lines: int,
    max_overlap_fraction: float,
) -> None:
    if not isinstance(overlap_lines, int) or isinstance(overlap_lines, bool):
        raise ValueError("overlap_lines must be an integer >= 0")
    if overlap_lines < 0:
        raise ValueError("overlap_lines must be an integer >= 0")

    if not isinstance(max_overlap_lines, int) or isinstance(max_overlap_lines, bool):
        raise ValueError("max_overlap_lines must be an integer >= 1")
    if max_overlap_lines < 1:
        raise ValueError("max_overlap_lines must be an integer >= 1")

    if not isinstance(max_overlap_fraction, (int, float)) or isinstance(
        max_overlap_fraction, bool
    ):
        raise ValueError("max_overlap_fraction must be > 0 and <= 1")
    if not math.isfinite(float(max_overlap_fraction)):
        raise ValueError("max_overlap_fraction must be finite")
    if not 0 < float(max_overlap_fraction) <= 1:
        raise ValueError("max_overlap_fraction must be > 0 and <= 1")


def _required_attr(chunk: Any, name: str) -> Any:
    if not hasattr(chunk, name):
        raise ValueError(f"chunk must expose {name}")
    return getattr(chunk, name)


def _semantic_compatible(previous: Any, current: Any) -> bool:
    for attribute in ("kind", "marker"):
        if hasattr(previous, attribute) and hasattr(current, attribute):
            if getattr(previous, attribute) != getattr(current, attribute):
                return False
    return True


def _base_view(chunk: Any) -> ControlledOverlapChunk:
    ordinal = _required_attr(chunk, "ordinal")
    content = _required_attr(chunk, "content")
    line_start = _required_attr(chunk, "line_start")
    line_end = _required_attr(chunk, "line_end")

    return ControlledOverlapChunk(
        source_ordinal=ordinal,
        content=content,
        primary_content=content,
        primary_line_start=line_start,
        primary_line_end=line_end,
    )


def apply_controlled_overlap(
    chunks: Sequence[Any],
    *,
    overlap_lines: int = 2,
    max_overlap_lines: int = 4,
    max_overlap_fraction: float = 0.25,
) -> Tuple[ControlledOverlapChunk, ...]:
    """Create overlap views only for forced continuation chunks.

    Source chunks are never mutated.
    """

    _validate_policy(
        overlap_lines,
        max_overlap_lines,
        max_overlap_fraction,
    )

    if not isinstance(chunks, Sequence):
        raise ValueError("chunks must be a sequence")

    views = []
    for index, current in enumerate(chunks):
        current_view = _base_view(current)

        if index == 0 or overlap_lines == 0:
            views.append(current_view)
            continue

        if not bool(getattr(current, "continuation", False)):
            views.append(current_view)
            continue

        previous = chunks[index - 1]
        previous_line_end = _required_attr(previous, "line_end")
        current_line_start = _required_attr(current, "line_start")

        if previous_line_end + 1 != current_line_start:
            views.append(current_view)
            continue

        if not _semantic_compatible(previous, current):
            views.append(current_view)
            continue

        previous_content = _required_attr(previous, "content")
        previous_lines = previous_content.splitlines()
        current_primary_lines = (
            current_view.primary_line_end
            - current_view.primary_line_start
            + 1
        )

        fractional_cap = max(
            1,
            int(current_primary_lines * float(max_overlap_fraction)),
        )
        count = min(
            overlap_lines,
            max_overlap_lines,
            fractional_cap,
            len(previous_lines),
        )

        if count <= 0:
            views.append(current_view)
            continue

        overlap_text = "\n".join(previous_lines[-count:])
        overlap_line_end = previous_line_end
        overlap_line_start = overlap_line_end - count + 1

        views.append(
            ControlledOverlapChunk(
                source_ordinal=current_view.source_ordinal,
                content=f"{overlap_text}\n{current_view.primary_content}",
                primary_content=current_view.primary_content,
                primary_line_start=current_view.primary_line_start,
                primary_line_end=current_view.primary_line_end,
                overlap_line_start=overlap_line_start,
                overlap_line_end=overlap_line_end,
                overlap_lines=count,
                reason=OverlapReason.FORCED_CONTINUATION,
            )
        )

    return tuple(views)
