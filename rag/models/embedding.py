"""Text embedding client for Jina v5 Text Small — RAG-006-D.

This module generates embeddings only. It does not load models implicitly,
cache vectors, persist vectors, or create a vector index.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import math
from typing import (
    Callable,
    Iterable,
    List,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    Tuple,
)
from urllib.request import Request, urlopen

from rag.contracts import Chunk, SourceMetadata, SourceType

from .backend_policy import SELECTED_TEXT_BACKEND
from .lifecycle import ModelLifecycleState, TextModelLifecycle


TEXT_EMBEDDING_DIMENSION = 1024
TEXT_EMBEDDING_NORM_TARGET = 1.0
TEXT_EMBEDDING_NORM_TOLERANCE = 1e-3
TEXT_EMBEDDING_DETERMINISM_MIN_COSINE = 0.9999
TEXT_EMBEDDING_BATCH_SIZE = 1

_CACHE_NAMESPACE_PAYLOAD = "|".join(
    (
        "RAG_TEXT_EMBEDDING_CACHE_V1",
        SELECTED_TEXT_BACKEND.model_repository,
        str(SELECTED_TEXT_BACKEND.artifact_pin.revision),
        str(SELECTED_TEXT_BACKEND.artifact_pin.sha256),
        str(SELECTED_TEXT_BACKEND.artifact_pin.quantization),
        SELECTED_TEXT_BACKEND.pooling,
        SELECTED_TEXT_BACKEND.document_prefix,
        str(TEXT_EMBEDDING_DIMENSION),
    )
)
TEXT_EMBEDDING_CACHE_NAMESPACE = hashlib.sha256(
    _CACHE_NAMESPACE_PAYLOAD.encode("utf-8")
).hexdigest()

TEXT_DOCUMENT_SOURCE_TYPES: Tuple[SourceType, ...] = (
    SourceType.DOCUMENTATION,
    SourceType.AUDIT,
    SourceType.LOG,
    SourceType.GIT,
    SourceType.EXECUTION,
)


class TextEmbeddingRole(str, Enum):
    QUERY = "QUERY"
    DOCUMENT = "DOCUMENT"


class TextEmbeddingError(RuntimeError):
    pass


class TextEmbeddingStateError(TextEmbeddingError):
    pass


class TextEmbeddingProtocolError(TextEmbeddingError):
    pass


class TextEmbeddingValidationError(TextEmbeddingError):
    pass


@dataclass(frozen=True)
class TextEmbeddingVector:
    role: TextEmbeddingRole
    values: Tuple[float, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.role, TextEmbeddingRole):
            raise ValueError("role must be TextEmbeddingRole")
        if len(self.values) != TEXT_EMBEDDING_DIMENSION:
            raise ValueError(
                f"embedding must contain exactly "
                f"{TEXT_EMBEDDING_DIMENSION} values"
            )
        for value in self.values:
            if not math.isfinite(float(value)):
                raise ValueError(
                    "embedding values must be finite"
                )

    @property
    def dimension(self) -> int:
        return len(self.values)

    @property
    def norm(self) -> float:
        return math.sqrt(
            sum(value * value for value in self.values)
        )


class DocumentEmbeddingCacheProtocol(Protocol):
    def get(
        self,
        *,
        namespace: str,
        chunk_sha256: str,
        dimension: int,
    ) -> Optional[Tuple[float, ...]]:
        ...

    def put(
        self,
        *,
        namespace: str,
        chunk_sha256: str,
        dimension: int,
        values: Sequence[float],
    ) -> None:
        ...


def chunk_content_sha256(content: str) -> str:
    if not isinstance(content, str):
        raise ValueError("content must be a string")
    return hashlib.sha256(
        content.encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class DocumentChunkEmbedding:
    chunk_id: str
    document_id: str
    metadata: SourceMetadata
    embedding: TextEmbeddingVector

    def __post_init__(self) -> None:
        if not isinstance(self.chunk_id, str) or not self.chunk_id.strip():
            raise ValueError("chunk_id must be non-empty")
        if not isinstance(self.document_id, str) or not self.document_id.strip():
            raise ValueError("document_id must be non-empty")
        if not isinstance(self.metadata, SourceMetadata):
            raise ValueError("metadata must be SourceMetadata")
        if self.embedding.role is not TextEmbeddingRole.DOCUMENT:
            raise ValueError(
                "document chunk embedding must use DOCUMENT role"
            )


@dataclass(frozen=True)
class CachedDocumentChunkEmbedding:
    result: DocumentChunkEmbedding
    chunk_sha256: str
    cache_hit: bool

    def __post_init__(self) -> None:
        if not isinstance(
            self.result,
            DocumentChunkEmbedding,
        ):
            raise ValueError(
                "result must be DocumentChunkEmbedding"
            )
        if (
            len(self.chunk_sha256) != 64
            or any(
                char not in "0123456789abcdef"
                for char in self.chunk_sha256
            )
        ):
            raise ValueError(
                "chunk_sha256 must be 64 lowercase hexadecimal characters"
            )


HttpOpener = Callable[..., object]


def cosine_similarity(
    first: Sequence[float],
    second: Sequence[float],
) -> float:
    if len(first) != len(second) or not first:
        raise ValueError(
            "vectors must be non-empty and have equal dimensions"
        )

    dot = 0.0
    first_norm_sq = 0.0
    second_norm_sq = 0.0

    for left, right in zip(first, second):
        left_value = float(left)
        right_value = float(right)
        if (
            not math.isfinite(left_value)
            or not math.isfinite(right_value)
        ):
            raise ValueError(
                "vectors must contain finite values"
            )
        dot += left_value * right_value
        first_norm_sq += left_value * left_value
        second_norm_sq += right_value * right_value

    if first_norm_sq == 0.0 or second_norm_sq == 0.0:
        raise ValueError(
            "cosine similarity requires non-zero vectors"
        )

    return dot / math.sqrt(
        first_norm_sq * second_norm_sq
    )


def embeddings_are_deterministic(
    first: TextEmbeddingVector,
    second: TextEmbeddingVector,
    *,
    min_cosine: float = TEXT_EMBEDDING_DETERMINISM_MIN_COSINE,
) -> bool:
    if first.role is not second.role:
        return False
    if not -1.0 <= min_cosine <= 1.0:
        raise ValueError(
            "min_cosine must be between -1 and 1"
        )
    return (
        cosine_similarity(
            first.values,
            second.values,
        )
        >= min_cosine
    )


def _require_text(
    value: str,
    field_name: str,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"{field_name} must be a non-empty string"
        )
    return value


def _prefix_for_role(
    role: TextEmbeddingRole,
) -> str:
    if role is TextEmbeddingRole.QUERY:
        return SELECTED_TEXT_BACKEND.query_prefix
    if role is TextEmbeddingRole.DOCUMENT:
        return SELECTED_TEXT_BACKEND.document_prefix
    raise ValueError("unsupported embedding role")


class TextEmbeddingClient:
    def __init__(
        self,
        lifecycle: TextModelLifecycle,
        *,
        opener: HttpOpener = urlopen,
        timeout_seconds: float = 30.0,
    ) -> None:
        if not isinstance(lifecycle, TextModelLifecycle):
            raise ValueError(
                "lifecycle must be TextModelLifecycle"
            )
        if timeout_seconds <= 0:
            raise ValueError(
                "timeout_seconds must be > 0"
            )

        self._lifecycle = lifecycle
        self._opener = opener
        self._timeout_seconds = float(
            timeout_seconds
        )

    def _endpoint(self) -> str:
        snapshot = self._lifecycle.snapshot()
        if snapshot.state is not ModelLifecycleState.READY:
            raise TextEmbeddingStateError(
                "text model must be READY before embedding"
            )
        if (
            not snapshot.process_alive
            or snapshot.port is None
        ):
            raise TextEmbeddingStateError(
                "text model READY snapshot is not usable"
            )

        return (
            f"http://{snapshot.host}:"
            f"{snapshot.port}"
            f"{SELECTED_TEXT_BACKEND.embeddings_endpoint}"
        )

    def _request_one(
        self,
        text: str,
        role: TextEmbeddingRole,
    ) -> TextEmbeddingVector:
        raw_text = _require_text(
            text,
            "text",
        )
        prefix = _prefix_for_role(role)
        payload = json.dumps(
            {
                "input": prefix + raw_text,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")

        request = Request(
            self._endpoint(),
            data=payload,
            headers={
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with self._opener(
                request,
                timeout=self._timeout_seconds,
            ) as response:
                body = response.read()
        except Exception as exc:
            raise TextEmbeddingProtocolError(
                f"embedding request failed: {exc}"
            ) from exc

        try:
            decoded = json.loads(
                body.decode("utf-8")
            )
        except Exception as exc:
            raise TextEmbeddingProtocolError(
                "embedding response is not valid UTF-8 JSON"
            ) from exc

        vector = self._parse_response(
            decoded,
            role,
        )
        self._validate_vector(vector)
        return vector

    def _parse_response(
        self,
        payload: object,
        role: TextEmbeddingRole,
    ) -> TextEmbeddingVector:
        if not isinstance(payload, Mapping):
            raise TextEmbeddingProtocolError(
                "embedding response must be an object"
            )

        data = payload.get("data")
        if (
            not isinstance(data, list)
            or len(data) != 1
        ):
            raise TextEmbeddingProtocolError(
                "embedding response must contain exactly one data item"
            )

        item = data[0]
        if not isinstance(item, Mapping):
            raise TextEmbeddingProtocolError(
                "embedding data item must be an object"
            )

        index = item.get("index")
        if index != 0:
            raise TextEmbeddingProtocolError(
                "embedding response index must be 0"
            )

        values = item.get("embedding")
        if not isinstance(values, list):
            raise TextEmbeddingProtocolError(
                "embedding item must contain a list vector"
            )

        try:
            converted = tuple(
                float(value)
                for value in values
            )
        except (TypeError, ValueError) as exc:
            raise TextEmbeddingProtocolError(
                "embedding vector contains a non-numeric value"
            ) from exc

        try:
            return TextEmbeddingVector(
                role=role,
                values=converted,
            )
        except ValueError as exc:
            raise TextEmbeddingValidationError(
                str(exc)
            ) from exc

    def _validate_vector(
        self,
        vector: TextEmbeddingVector,
    ) -> None:
        if (
            abs(
                vector.norm
                - TEXT_EMBEDDING_NORM_TARGET
            )
            > TEXT_EMBEDDING_NORM_TOLERANCE
        ):
            raise TextEmbeddingValidationError(
                "embedding is not unit normalized within tolerance"
            )

    def embed_query(
        self,
        text: str,
    ) -> TextEmbeddingVector:
        return self._request_one(
            text,
            TextEmbeddingRole.QUERY,
        )

    def embed_document(
        self,
        text: str,
    ) -> TextEmbeddingVector:
        return self._request_one(
            text,
            TextEmbeddingRole.DOCUMENT,
        )

    def embed_documents(
        self,
        texts: Iterable[str],
    ) -> Tuple[TextEmbeddingVector, ...]:
        # RAG-006-D deliberately uses one request per document.
        # Real GPU probing showed exact sequential repeatability while
        # duplicate inputs in the same llama.cpp batch can differ slightly.
        items = tuple(texts)
        return tuple(
            self.embed_document(text)
            for text in items
        )

    def _validate_text_chunk(
        self,
        chunk: Chunk,
    ) -> None:
        if not isinstance(chunk, Chunk):
            raise ValueError(
                "chunks must contain only Chunk values"
            )
        if (
            chunk.metadata.source_type
            not in TEXT_DOCUMENT_SOURCE_TYPES
        ):
            raise TextEmbeddingValidationError(
                "chunk source_type is outside the text-model corpus"
            )

    def embed_document_chunks(
        self,
        chunks: Iterable[Chunk],
    ) -> Tuple[DocumentChunkEmbedding, ...]:
        results: List[
            DocumentChunkEmbedding
        ] = []

        for chunk in chunks:
            self._validate_text_chunk(chunk)

            results.append(
                DocumentChunkEmbedding(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    metadata=chunk.metadata,
                    embedding=self.embed_document(
                        chunk.content
                    ),
                )
            )

        return tuple(results)


    def embed_document_chunks_cached(
        self,
        chunks: Iterable[Chunk],
        cache: DocumentEmbeddingCacheProtocol,
    ) -> Tuple[CachedDocumentChunkEmbedding, ...]:
        results: List[
            CachedDocumentChunkEmbedding
        ] = []

        if not hasattr(cache, "get") or not hasattr(
            cache,
            "put",
        ):
            raise ValueError(
                "cache must provide get and put methods"
            )

        for chunk in chunks:
            self._validate_text_chunk(chunk)
            chunk_sha = chunk_content_sha256(
                chunk.content
            )

            cached_values = cache.get(
                namespace=TEXT_EMBEDDING_CACHE_NAMESPACE,
                chunk_sha256=chunk_sha,
                dimension=TEXT_EMBEDDING_DIMENSION,
            )

            if cached_values is None:
                vector = self.embed_document(
                    chunk.content
                )
                cache.put(
                    namespace=TEXT_EMBEDDING_CACHE_NAMESPACE,
                    chunk_sha256=chunk_sha,
                    dimension=TEXT_EMBEDDING_DIMENSION,
                    values=vector.values,
                )
                cache_hit = False
            else:
                try:
                    vector = TextEmbeddingVector(
                        role=TextEmbeddingRole.DOCUMENT,
                        values=tuple(
                            cached_values
                        ),
                    )
                except ValueError as exc:
                    raise TextEmbeddingValidationError(
                        f"cached embedding is invalid: {exc}"
                    ) from exc
                self._validate_vector(vector)
                cache_hit = True

            result = DocumentChunkEmbedding(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                metadata=chunk.metadata,
                embedding=vector,
            )
            results.append(
                CachedDocumentChunkEmbedding(
                    result=result,
                    chunk_sha256=chunk_sha,
                    cache_hit=cache_hit,
                )
            )

        return tuple(results)
