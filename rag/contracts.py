"""Stable data contracts for the CodeBridge 2.0 RAG layer.

RAG-001-C intentionally uses only the Python standard library.
Importing this module must not load models, touch indexes, open databases,
start servers, or execute shell commands.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
import re
from typing import Optional, Tuple


_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


class SourceType(str, Enum):
    DOCUMENTATION = "DOCUMENTATION"
    CODE = "CODE"
    GIT = "GIT"
    AUDIT = "AUDIT"
    LOG = "LOG"
    EXECUTION = "EXECUTION"
    OTHER = "OTHER"


class ModelState(str, Enum):
    UNLOADED = "UNLOADED"
    LOADING = "LOADING"
    READY = "READY"
    IDLE = "IDLE"
    UNLOADING = "UNLOADING"
    ERROR = "ERROR"


class IndexState(str, Enum):
    UNAVAILABLE = "UNAVAILABLE"
    EMPTY = "EMPTY"
    INDEXING = "INDEXING"
    READY = "READY"
    STALE = "STALE"
    ERROR = "ERROR"


@dataclass(frozen=True)
class SourceMetadata:
    project_id: str
    source_type: SourceType
    path: Optional[str] = None
    symbol: Optional[str] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    git_branch: Optional[str] = None
    git_commit: Optional[str] = None
    git_provenance_commit: Optional[str] = None
    git_worktree_status: Optional[str] = None
    sha256: Optional[str] = None
    indexed_at: Optional[str] = None
    source_id: Optional[str] = None

    def __post_init__(self) -> None:
        _require_text(self.project_id, "project_id")
        if not isinstance(self.source_type, SourceType):
            raise ValueError("source_type must be a SourceType")

        if self.line_start is not None and self.line_start < 1:
            raise ValueError("line_start must be >= 1")
        if self.line_end is not None:
            if self.line_start is None:
                raise ValueError("line_end requires line_start")
            if self.line_end < self.line_start:
                raise ValueError("line_end must be >= line_start")

        if self.sha256 is not None and not _SHA256_RE.fullmatch(self.sha256):
            raise ValueError("sha256 must contain exactly 64 hexadecimal characters")


@dataclass(frozen=True)
class Document:
    document_id: str
    content: str
    metadata: SourceMetadata

    def __post_init__(self) -> None:
        _require_text(self.document_id, "document_id")
        if not isinstance(self.content, str):
            raise ValueError("content must be a string")
        if not isinstance(self.metadata, SourceMetadata):
            raise ValueError("metadata must be SourceMetadata")


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    document_id: str
    content: str
    metadata: SourceMetadata
    ordinal: int = 0
    parent_chunk_id: Optional[str] = None

    def __post_init__(self) -> None:
        _require_text(self.chunk_id, "chunk_id")
        _require_text(self.document_id, "document_id")
        _require_text(self.content, "content")
        if not isinstance(self.metadata, SourceMetadata):
            raise ValueError("metadata must be SourceMetadata")
        if self.ordinal < 0:
            raise ValueError("ordinal must be >= 0")


@dataclass(frozen=True)
class SearchQuery:
    query: str
    project_id: str
    source_types: Tuple[SourceType, ...] = ()
    top_k: int = 10
    path_filter: Optional[str] = None
    branch: Optional[str] = None

    def __post_init__(self) -> None:
        _require_text(self.query, "query")
        _require_text(self.project_id, "project_id")
        if self.top_k < 1:
            raise ValueError("top_k must be >= 1")
        if any(not isinstance(item, SourceType) for item in self.source_types):
            raise ValueError("source_types must contain only SourceType values")


@dataclass(frozen=True)
class SearchResult:
    chunk_id: str
    document_id: str
    content: str
    metadata: SourceMetadata
    score: float
    rank: int
    retrieval_modes: Tuple[str, ...] = ()
    stale: bool = False

    def __post_init__(self) -> None:
        _require_text(self.chunk_id, "chunk_id")
        _require_text(self.document_id, "document_id")
        if not isinstance(self.content, str):
            raise ValueError("content must be a string")
        if not isinstance(self.metadata, SourceMetadata):
            raise ValueError("metadata must be SourceMetadata")
        if not math.isfinite(float(self.score)):
            raise ValueError("score must be finite")
        if self.rank < 1:
            raise ValueError("rank must be >= 1")
        if any(not isinstance(mode, str) or not mode.strip() for mode in self.retrieval_modes):
            raise ValueError("retrieval_modes must contain non-empty strings")
