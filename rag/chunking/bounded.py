"""Bound chunks for Jina indexing without changing source files

Structural chunkers choose the semantic boundaries first
This final pass only divides chunks that exceed the model input budget
Character limits are conservative safeguards rather than token counts
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Iterable, Tuple


CODE_INDEX_MAX_CHARS = 1024
TEXT_INDEX_MAX_CHARS = 2048


def bound_index_chunks(
    drafts: Iterable[Any],
    *,
    max_chars: int,
) -> Tuple[Any, ...]:
    """Keep the exact indexed content and source line ranges with bounded pieces

    A minified single source line can produce multiple pieces on the same line
    The source line number remains correct but no column metadata is available
    Fail rather than discard content if it cannot fit into a nonblank piece
    """
    if type(max_chars) is not int or max_chars < 1:
        raise ValueError("max_chars must be a positive integer")

    bounded = []
    for draft in drafts:
        content = draft.content
        if not isinstance(content, str) or not content.strip():
            raise ValueError("chunk content must not be blank")

        offset = 0
        while offset < len(content):
            end = min(len(content), offset + max_chars)
            if end < len(content):
                # Prefer a nearby source line boundary over splitting syntax
                last_newline = content.rfind(
                    "\n", offset + max_chars // 2, end
                )
                if last_newline >= offset:
                    end = last_newline + 1

            part = content[offset:end]
            if not part.strip():
                raise ValueError(
                    "cannot preserve an oversized whitespace-only chunk "
                    "under the configured bound"
                )

            preceding_lines = content.count("\n", 0, offset)
            part_lines = part.count("\n")
            line_start = draft.line_start + preceding_lines
            line_end = line_start + part_lines - int(part.endswith("\n"))
            if not (draft.line_start <= line_start <= line_end <= draft.line_end):
                raise ValueError("bounded chunk line range is inconsistent")

            updates = {
                "ordinal": len(bounded),
                "content": part,
                "line_start": line_start,
                "line_end": line_end,
            }
            if hasattr(draft, "continuation") and offset:
                updates["continuation"] = True
            bounded.append(replace(draft, **updates))
            offset = end

    return tuple(bounded)
