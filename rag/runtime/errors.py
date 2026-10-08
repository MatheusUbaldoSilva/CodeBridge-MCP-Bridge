"""Stable public RAG error contract for MCP tools — RAG-013-E."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RagPublicErrorType(str, Enum):
    MODEL_LOAD = "MODEL_LOAD"
    INDEX_UNAVAILABLE = "INDEX_UNAVAILABLE"
    SOURCE_MISSING = "SOURCE_MISSING"
    STALE_RESULT = "STALE_RESULT"
    INVALID_SCOPE = "INVALID_SCOPE"
    EXECUTOR_UNAVAILABLE = "EXECUTOR_UNAVAILABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class RagStaleResultError(RuntimeError):
    pass


@dataclass(frozen=True)
class RagPublicError:
    error_type: RagPublicErrorType
    message: str
    retryable: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "error_type": self.error_type.value,
            "error_message": self.message,
            "retryable": self.retryable,
        }


_MODEL_LOAD_NAMES = frozenset(
    {
        "ModelLoadError",
        "ModelFallbackError",
        "ModelFallbackExhaustedError",
        "TextEmbeddingStateError",
        "TextEmbeddingProtocolError",
        "CodeEmbeddingStateError",
        "CodeEmbeddingProtocolError",
    }
)

_INDEX_UNAVAILABLE_NAMES = frozenset(
    {
        "RagSearchIndexUnavailableError",
        "RagContextIndexUnavailableError",
        "RagSchemaVersionError",
        "RagSchemaIntegrityError",
        "RagFts5UnavailableError",
        "QdrantLocalError",
    }
)

_SOURCE_MISSING_NAMES = frozenset(
    {
        "RagContextSourceMissingError",
        "FileNotFoundError",
    }
)

_INVALID_SCOPE_NAMES = frozenset(
    {
        "RagContextInvalidScopeError",
        "ValueError",
    }
)


def classify_rag_error(exc: BaseException) -> RagPublicError:
    if not isinstance(exc, BaseException):
        raise ValueError("exc must be an exception")

    name = type(exc).__name__
    message = str(exc).strip() or name

    if isinstance(exc, RagStaleResultError) or name == "RagStaleResultError":
        return RagPublicError(
            error_type=RagPublicErrorType.STALE_RESULT,
            message=message,
            retryable=False,
        )

    if name == "RagIndexExecutionUnavailableError":
        return RagPublicError(
            error_type=RagPublicErrorType.EXECUTOR_UNAVAILABLE,
            message=message,
            retryable=True,
        )

    if name in _MODEL_LOAD_NAMES:
        return RagPublicError(
            error_type=RagPublicErrorType.MODEL_LOAD,
            message=message,
            retryable=True,
        )

    if name in _INDEX_UNAVAILABLE_NAMES:
        return RagPublicError(
            error_type=RagPublicErrorType.INDEX_UNAVAILABLE,
            message=message,
            retryable=True,
        )

    if name in _SOURCE_MISSING_NAMES:
        return RagPublicError(
            error_type=RagPublicErrorType.SOURCE_MISSING,
            message=message,
            retryable=False,
        )

    if name in _INVALID_SCOPE_NAMES:
        return RagPublicError(
            error_type=RagPublicErrorType.INVALID_SCOPE,
            message=message,
            retryable=False,
        )

    return RagPublicError(
        error_type=RagPublicErrorType.INTERNAL_ERROR,
        message=message,
        retryable=False,
    )
