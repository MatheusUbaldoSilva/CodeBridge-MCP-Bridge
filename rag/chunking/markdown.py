"""Deterministic Markdown chunking for RAG-003-A.

Strategy order:
1. Markdown heading boundaries
2. subsection hierarchy
3. logical blocks separated by blank lines

No overlap, indexing, embeddings, model loading, filesystem I/O, or shell execution
is performed here. Full source provenance is completed in RAG-003-D.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import List, Optional, Sequence, Tuple


class MarkdownChunkKind(str, Enum):
    PREAMBLE = "PREAMBLE"
    SECTION = "SECTION"


@dataclass(frozen=True)
class MarkdownChunkDraft:
    ordinal: int
    content: str
    heading_path: Tuple[str, ...]
    heading_level: Optional[int]
    line_start: int
    line_end: int
    kind: MarkdownChunkKind

    def __post_init__(self) -> None:
        if self.ordinal < 0:
            raise ValueError("ordinal must be >= 0")
        if not isinstance(self.content, str) or not self.content.strip():
            raise ValueError("content must be a non-empty string")
        if self.heading_level is not None and not 1 <= self.heading_level <= 6:
            raise ValueError("heading_level must be between 1 and 6")
        if self.line_start < 1:
            raise ValueError("line_start must be >= 1")
        if self.line_end < self.line_start:
            raise ValueError("line_end must be >= line_start")
        if not isinstance(self.kind, MarkdownChunkKind):
            raise ValueError("kind must be MarkdownChunkKind")


_ATX_HEADING_RE = re.compile(
    r"^\s{0,3}(#{1,6})(?:[ \t]+|$)(.*)$"
)
_SETEXT_UNDERLINE_RE = re.compile(
    r"^\s{0,3}(=+|-+)\s*$"
)
_FENCE_OPEN_RE = re.compile(
    r"^\s{0,3}(`{3,}|~{3,})(.*)$"
)
_CLOSING_HASHES_RE = re.compile(
    r"[ \t]+#+[ \t]*$"
)


@dataclass(frozen=True)
class _Heading:
    start: int
    end: int
    level: int
    title: str


def _fence_mask(lines: Sequence[str]) -> List[bool]:
    mask = [False] * len(lines)
    open_char: Optional[str] = None
    open_len = 0

    for index, line in enumerate(lines):
        if open_char is None:
            match = _FENCE_OPEN_RE.match(line)
            if match:
                token = match.group(1)
                open_char = token[0]
                open_len = len(token)
                mask[index] = True
            continue

        mask[index] = True
        stripped = line.lstrip()
        if not stripped.startswith(open_char * open_len):
            continue

        run = 0
        while run < len(stripped) and stripped[run] == open_char:
            run += 1
        if run < open_len:
            continue
        if stripped[run:].strip():
            continue

        open_char = None
        open_len = 0

    return mask


def _clean_atx_title(raw: str) -> str:
    title = str(raw or "").strip()
    title = _CLOSING_HASHES_RE.sub("", title).strip()
    return title


def _heading_events(
    lines: Sequence[str],
    fence_mask: Sequence[bool],
) -> List[_Heading]:
    headings: List[_Heading] = []
    index = 0

    while index < len(lines):
        if fence_mask[index]:
            index += 1
            continue

        atx = _ATX_HEADING_RE.match(lines[index])
        if atx:
            title = _clean_atx_title(atx.group(2))
            if title:
                headings.append(
                    _Heading(
                        start=index,
                        end=index,
                        level=len(atx.group(1)),
                        title=title,
                    )
                )
            index += 1
            continue

        if (
            index + 1 < len(lines)
            and not fence_mask[index + 1]
            and lines[index].strip()
        ):
            setext = _SETEXT_UNDERLINE_RE.match(lines[index + 1])
            if setext:
                headings.append(
                    _Heading(
                        start=index,
                        end=index + 1,
                        level=1 if setext.group(1)[0] == "=" else 2,
                        title=lines[index].strip(),
                    )
                )
                index += 2
                continue

        index += 1

    return headings


def _logical_blocks(
    lines: Sequence[str],
    start: int,
    end: int,
    fence_mask: Sequence[bool],
) -> List[Tuple[int, int]]:
    if start > end:
        return []

    blocks: List[Tuple[int, int]] = []
    index = start

    while index <= end:
        while (
            index <= end
            and not fence_mask[index]
            and not lines[index].strip()
        ):
            index += 1

        if index > end:
            break

        block_start = index
        index += 1

        while index <= end:
            if not fence_mask[index] and not lines[index].strip():
                break
            index += 1

        blocks.append((block_start, index - 1))

        while (
            index <= end
            and not fence_mask[index]
            and not lines[index].strip()
        ):
            index += 1

    return blocks


def _source_slice(
    lines: Sequence[str],
    start: int,
    end: int,
) -> str:
    return "\n".join(lines[start:end + 1]).strip("\n")


def chunk_markdown(text: str) -> Tuple[MarkdownChunkDraft, ...]:
    """Split Markdown into deterministic heading-aware logical chunks.

    Line numbers are 1-based parser coordinates.
    They are not yet the full provenance contract from RAG-003-D.
    """

    if not isinstance(text, str):
        raise ValueError("text must be a string")

    lines = text.splitlines()
    if not lines or not any(line.strip() for line in lines):
        return ()

    fence_mask = _fence_mask(lines)
    headings = _heading_events(lines, fence_mask)

    chunks: List[MarkdownChunkDraft] = []
    ordinal = 0

    first_heading_start = headings[0].start if headings else len(lines)
    for block_start, block_end in _logical_blocks(
        lines,
        0,
        first_heading_start - 1,
        fence_mask,
    ):
        chunks.append(
            MarkdownChunkDraft(
                ordinal=ordinal,
                content=_source_slice(lines, block_start, block_end),
                heading_path=(),
                heading_level=None,
                line_start=block_start + 1,
                line_end=block_end + 1,
                kind=MarkdownChunkKind.PREAMBLE,
            )
        )
        ordinal += 1

    heading_stack: List[str] = []

    for heading_index, heading in enumerate(headings):
        while len(heading_stack) >= heading.level:
            heading_stack.pop()

        while len(heading_stack) < heading.level - 1:
            heading_stack.append("")

        heading_stack.append(heading.title)
        heading_path = tuple(item for item in heading_stack if item)

        section_end = (
            headings[heading_index + 1].start - 1
            if heading_index + 1 < len(headings)
            else len(lines) - 1
        )

        body_blocks = _logical_blocks(
            lines,
            heading.end + 1,
            section_end,
            fence_mask,
        )

        if not body_blocks:
            chunks.append(
                MarkdownChunkDraft(
                    ordinal=ordinal,
                    content=_source_slice(
                        lines,
                        heading.start,
                        heading.end,
                    ),
                    heading_path=heading_path,
                    heading_level=heading.level,
                    line_start=heading.start + 1,
                    line_end=heading.end + 1,
                    kind=MarkdownChunkKind.SECTION,
                )
            )
            ordinal += 1
            continue

        first_block_start, first_block_end = body_blocks[0]
        chunks.append(
            MarkdownChunkDraft(
                ordinal=ordinal,
                content=_source_slice(
                    lines,
                    heading.start,
                    first_block_end,
                ),
                heading_path=heading_path,
                heading_level=heading.level,
                line_start=heading.start + 1,
                line_end=first_block_end + 1,
                kind=MarkdownChunkKind.SECTION,
            )
        )
        ordinal += 1

        for block_start, block_end in body_blocks[1:]:
            chunks.append(
                MarkdownChunkDraft(
                    ordinal=ordinal,
                    content=_source_slice(lines, block_start, block_end),
                    heading_path=heading_path,
                    heading_level=heading.level,
                    line_start=block_start + 1,
                    line_end=block_end + 1,
                    kind=MarkdownChunkKind.SECTION,
                )
            )
            ordinal += 1

    return tuple(chunks)
