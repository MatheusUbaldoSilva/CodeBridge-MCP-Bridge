"""Source provenance binding for RAG-003-D.

This module attaches verified source provenance to text chunks produced by
RAG-003-A/B. It deliberately does not invent deterministic chunk IDs; that
belongs to RAG-009-D.

The SHA-256 is calculated from the complete source text using UTF-8 and every
draft line range is checked against the real source before a Chunk is emitted.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
from pathlib import PurePosixPath
import re
from typing import Any, Optional, Sequence, Tuple

from rag.contracts import Chunk, SourceMetadata, SourceType


_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:/")


def _required_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _normalized_relative_path(value: str) -> str:
    text = _required_text(value, "path").replace("\\", "/")
    if text.startswith("//") or _WINDOWS_DRIVE_RE.match(text):
        raise ValueError("path must be repository-relative")
    path = PurePosixPath(text)
    if path.is_absolute():
        raise ValueError("path must be repository-relative")
    if ".." in path.parts:
        raise ValueError("path traversal is not allowed")
    normalized = str(path)
    if normalized in ("", "."):
        raise ValueError("path must identify a source file")
    return normalized


def _validate_indexed_at(value: str) -> str:
    text = _required_text(value, "indexed_at")
    candidate = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ValueError("indexed_at must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError("indexed_at must include timezone information")
    return text


def source_sha256(source_text: str) -> str:
    if not isinstance(source_text, str):
        raise ValueError("source_text must be a string")
    return hashlib.sha256(source_text.encode("utf-8")).hexdigest()


def _draft_range(draft: Any) -> Tuple[int, int]:
    try:
        line_start = int(draft.line_start)
        line_end = int(draft.line_end)
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("draft must expose integer line_start and line_end") from exc

    if line_start < 1:
        raise ValueError("draft line_start must be >= 1")
    if line_end < line_start:
        raise ValueError("draft line_end must be >= line_start")
    return line_start, line_end


def _draft_content(draft: Any) -> str:
    try:
        content = draft.content
    except AttributeError as exc:
        raise ValueError("draft must expose content") from exc
    if not isinstance(content, str) or not content.strip():
        raise ValueError("draft content must be a non-empty string")
    return content


def _draft_ordinal(draft: Any) -> int:
    try:
        ordinal = int(draft.ordinal)
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("draft must expose integer ordinal") from exc
    if ordinal < 0:
        raise ValueError("draft ordinal must be >= 0")
    return ordinal


def _verify_source_slice(
    source_lines: Sequence[str],
    draft: Any,
) -> Tuple[int, int, str]:
    line_start, line_end = _draft_range(draft)
    if line_end > len(source_lines):
        raise ValueError("draft line range exceeds source text")

    expected = "\n".join(source_lines[line_start - 1:line_end])
    actual = _draft_content(draft)
    if expected != actual:
        raise ValueError(
            "draft content does not match source text at declared line range"
        )
    return line_start, line_end, actual


def attach_source_provenance(
    drafts: Sequence[Any],
    *,
    source_text: str,
    project_id: str,
    path: str,
    source_type: SourceType,
    indexed_at: str,
    document_id: str,
    chunk_ids: Sequence[str],
    git_branch: Optional[str] = None,
    git_commit: Optional[str] = None,
    source_id: Optional[str] = None,
) -> Tuple[Chunk, ...]:
    """Return immutable Chunk contracts with verified source provenance.

    chunk_ids are supplied by the caller on purpose. RAG-003-D must not freeze
    the deterministic ID policy reserved for RAG-009-D.
    """

    if not isinstance(drafts, Sequence):
        raise ValueError("drafts must be a sequence")
    if not isinstance(chunk_ids, Sequence) or isinstance(chunk_ids, (str, bytes)):
        raise ValueError("chunk_ids must be a sequence of strings")
    if len(drafts) != len(chunk_ids):
        raise ValueError("chunk_ids length must match drafts length")

    _required_text(project_id, "project_id")
    normalized_path = _normalized_relative_path(path)
    if not isinstance(source_type, SourceType):
        raise ValueError("source_type must be a SourceType")
    captured_at = _validate_indexed_at(indexed_at)
    doc_id = _required_text(document_id, "document_id")

    if not isinstance(source_text, str):
        raise ValueError("source_text must be a string")

    digest = source_sha256(source_text)
    source_lines = source_text.splitlines()

    chunks = []
    seen_ids = set()
    seen_ordinals = set()

    for draft, chunk_id in zip(drafts, chunk_ids):
        cid = _required_text(chunk_id, "chunk_id")
        if cid in seen_ids:
            raise ValueError("chunk_ids must be unique")
        seen_ids.add(cid)

        ordinal = _draft_ordinal(draft)
        if ordinal in seen_ordinals:
            raise ValueError("draft ordinals must be unique")
        seen_ordinals.add(ordinal)

        line_start, line_end, content = _verify_source_slice(
            source_lines,
            draft,
        )

        metadata = SourceMetadata(
            project_id=project_id.strip(),
            source_type=source_type,
            path=normalized_path,
            line_start=line_start,
            line_end=line_end,
            git_branch=git_branch,
            git_commit=git_commit,
            sha256=digest,
            indexed_at=captured_at,
            source_id=source_id,
        )

        chunks.append(
            Chunk(
                chunk_id=cid,
                document_id=doc_id,
                content=content,
                metadata=metadata,
                ordinal=ordinal,
            )
        )

    return tuple(chunks)
