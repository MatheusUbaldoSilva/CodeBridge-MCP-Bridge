"""Source SHA staleness evaluation for RAG-011-D."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import hashlib
from pathlib import Path
from typing import Optional

from rag.contracts import SearchResult, SourceMetadata


class StalenessStatus(str, Enum):
    FRESH = "FRESH"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class StalenessEvaluation:
    status: StalenessStatus
    path: Optional[str]
    indexed_sha256: Optional[str]
    current_sha256: Optional[str]
    reason: str

    @property
    def stale(self) -> bool:
        return self.status is StalenessStatus.STALE


def _current_source_sha256(path: Path) -> str:
    content = path.read_text(encoding="utf-8")
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def evaluate_source_staleness(
    repository_root: str | Path,
    metadata: SourceMetadata,
) -> StalenessEvaluation:
    if not isinstance(metadata, SourceMetadata):
        raise ValueError("metadata must be SourceMetadata")

    if metadata.path is None:
        return StalenessEvaluation(
            status=StalenessStatus.UNKNOWN,
            path=None,
            indexed_sha256=metadata.sha256,
            current_sha256=None,
            reason="PATH_UNAVAILABLE",
        )

    if metadata.sha256 is None:
        return StalenessEvaluation(
            status=StalenessStatus.UNKNOWN,
            path=metadata.path,
            indexed_sha256=None,
            current_sha256=None,
            reason="INDEXED_SHA_UNAVAILABLE",
        )

    root = Path(repository_root).expanduser().resolve()
    candidate = (root / metadata.path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("metadata path must stay inside repository_root") from exc

    if not candidate.exists():
        return StalenessEvaluation(
            status=StalenessStatus.STALE,
            path=metadata.path,
            indexed_sha256=metadata.sha256,
            current_sha256=None,
            reason="FILE_MISSING",
        )

    if not candidate.is_file():
        return StalenessEvaluation(
            status=StalenessStatus.STALE,
            path=metadata.path,
            indexed_sha256=metadata.sha256,
            current_sha256=None,
            reason="NOT_A_FILE",
        )

    try:
        current_sha = _current_source_sha256(candidate)
    except (OSError, UnicodeError):
        return StalenessEvaluation(
            status=StalenessStatus.UNKNOWN,
            path=metadata.path,
            indexed_sha256=metadata.sha256,
            current_sha256=None,
            reason="READ_FAILED",
        )

    if current_sha == metadata.sha256:
        return StalenessEvaluation(
            status=StalenessStatus.FRESH,
            path=metadata.path,
            indexed_sha256=metadata.sha256,
            current_sha256=current_sha,
            reason="SHA_MATCH",
        )

    return StalenessEvaluation(
        status=StalenessStatus.STALE,
        path=metadata.path,
        indexed_sha256=metadata.sha256,
        current_sha256=current_sha,
        reason="SHA_MISMATCH",
    )


def mark_search_result_staleness(
    result: SearchResult,
    evaluation: StalenessEvaluation,
) -> SearchResult:
    if not isinstance(result, SearchResult):
        raise ValueError("result must be SearchResult")
    if not isinstance(evaluation, StalenessEvaluation):
        raise ValueError("evaluation must be StalenessEvaluation")
    if (
        result.metadata.path is not None
        and evaluation.path is not None
        and result.metadata.path != evaluation.path
    ):
        raise ValueError("result path conflicts with staleness evaluation")

    return replace(
        result,
        stale=evaluation.stale,
    )
