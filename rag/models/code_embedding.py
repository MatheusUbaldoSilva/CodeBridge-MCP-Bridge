"""Task-aware code embeddings for Jina Code 1.5B — RAG-007-C."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
import math
from typing import Callable, Iterable, List, Mapping, Sequence, Tuple
from urllib.request import Request, urlopen

from rag.contracts import Chunk, SourceMetadata, SourceType

from .code_backend_policy import (
    CODE_TASK_INSTRUCTIONS,
    SELECTED_CODE_BACKEND,
    CodeRetrievalTask,
)
from .code_lifecycle import CodeModelLifecycle
from .embedding import cosine_similarity
from .lifecycle import ModelLifecycleState


CODE_EMBEDDING_DIMENSION = 1536
CODE_EMBEDDING_NORM_TARGET = 1.0
CODE_EMBEDDING_NORM_TOLERANCE = 1e-3
CODE_EMBEDDING_DETERMINISM_MIN_COSINE = 0.9999
CODE_EMBEDDING_BATCH_SIZE = 1
CODE_CORPUS_SOURCE_TYPES: Tuple[SourceType, ...] = (SourceType.CODE,)
CODE_CORPUS_TASKS: Tuple[CodeRetrievalTask, ...] = (
    CodeRetrievalTask.NL2CODE,
    CodeRetrievalTask.CODE2CODE,
)


class CodeEmbeddingRole(str, Enum):
    QUERY = "QUERY"
    PASSAGE = "PASSAGE"


class CodeEmbeddingError(RuntimeError):
    pass


class CodeEmbeddingStateError(CodeEmbeddingError):
    pass


class CodeEmbeddingProtocolError(CodeEmbeddingError):
    pass


class CodeEmbeddingValidationError(CodeEmbeddingError):
    pass


@dataclass(frozen=True)
class CodeEmbeddingVector:
    task: CodeRetrievalTask
    role: CodeEmbeddingRole
    values: Tuple[float, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.task, CodeRetrievalTask):
            raise ValueError("task must be CodeRetrievalTask")
        if not isinstance(self.role, CodeEmbeddingRole):
            raise ValueError("role must be CodeEmbeddingRole")
        if len(self.values) != CODE_EMBEDDING_DIMENSION:
            raise ValueError(
                f"embedding must contain exactly {CODE_EMBEDDING_DIMENSION} values"
            )
        if any(not math.isfinite(float(value)) for value in self.values):
            raise ValueError("embedding values must be finite")

    @property
    def dimension(self) -> int:
        return len(self.values)

    @property
    def norm(self) -> float:
        return math.sqrt(sum(value * value for value in self.values))


@dataclass(frozen=True)
class CodeChunkEmbedding:
    chunk_id: str
    document_id: str
    metadata: SourceMetadata
    task: CodeRetrievalTask
    embedding: CodeEmbeddingVector

    def __post_init__(self) -> None:
        if not self.chunk_id.strip() or not self.document_id.strip():
            raise ValueError("chunk and document identifiers must be non-empty")
        if not isinstance(self.metadata, SourceMetadata):
            raise ValueError("metadata must be SourceMetadata")
        if self.metadata.source_type is not SourceType.CODE:
            raise ValueError("code chunk embedding requires SourceType.CODE")
        if self.embedding.role is not CodeEmbeddingRole.PASSAGE:
            raise ValueError("code chunk embedding must use PASSAGE role")
        if self.embedding.task is not self.task:
            raise ValueError("embedding task must match chunk task")


HttpOpener = Callable[..., object]


def code_embeddings_are_deterministic(
    first: CodeEmbeddingVector,
    second: CodeEmbeddingVector,
    *,
    min_cosine: float = CODE_EMBEDDING_DETERMINISM_MIN_COSINE,
) -> bool:
    if first.task is not second.task or first.role is not second.role:
        return False
    if not -1.0 <= min_cosine <= 1.0:
        raise ValueError("min_cosine must be between -1 and 1")
    return cosine_similarity(first.values, second.values) >= min_cosine


def _require_text(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("text must be a non-empty string")
    return value


def _prefix(task: CodeRetrievalTask, role: CodeEmbeddingRole) -> str:
    if not isinstance(task, CodeRetrievalTask):
        raise ValueError("task must be CodeRetrievalTask")
    instruction = CODE_TASK_INSTRUCTIONS[task]
    if role is CodeEmbeddingRole.QUERY:
        return instruction.query_prefix
    if role is CodeEmbeddingRole.PASSAGE:
        return instruction.passage_prefix
    raise ValueError("unsupported code embedding role")


class CodeEmbeddingClient:
    def __init__(
        self,
        lifecycle: CodeModelLifecycle,
        *,
        opener: HttpOpener = urlopen,
        timeout_seconds: float = 60.0,
    ) -> None:
        if not isinstance(lifecycle, CodeModelLifecycle):
            raise ValueError("lifecycle must be CodeModelLifecycle")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")
        self._lifecycle = lifecycle
        self._opener = opener
        self._timeout_seconds = float(timeout_seconds)

    def _endpoint(self) -> str:
        snapshot = self._lifecycle.snapshot()
        if snapshot.state is not ModelLifecycleState.READY:
            raise CodeEmbeddingStateError(
                "code model must be READY before embedding"
            )
        if not snapshot.process_alive or snapshot.port is None:
            raise CodeEmbeddingStateError(
                "code model READY snapshot is not usable"
            )
        return (
            f"http://{snapshot.host}:{snapshot.port}"
            f"{SELECTED_CODE_BACKEND.embeddings_endpoint}"
        )

    def _request_one(
        self,
        text: str,
        *,
        task: CodeRetrievalTask,
        role: CodeEmbeddingRole,
    ) -> CodeEmbeddingVector:
        raw = _require_text(text)
        payload = json.dumps(
            {"input": _prefix(task, role) + raw},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        request = Request(
            self._endpoint(),
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with self._opener(request, timeout=self._timeout_seconds) as response:
                body = response.read()
        except Exception as exc:
            raise CodeEmbeddingProtocolError(
                f"embedding request failed: {exc}"
            ) from exc
        try:
            decoded = json.loads(body.decode("utf-8"))
        except Exception as exc:
            raise CodeEmbeddingProtocolError(
                "embedding response is not valid UTF-8 JSON"
            ) from exc
        vector = self._parse_response(decoded, task=task, role=role)
        self._validate_vector(vector)
        return vector

    def _parse_response(
        self,
        payload: object,
        *,
        task: CodeRetrievalTask,
        role: CodeEmbeddingRole,
    ) -> CodeEmbeddingVector:
        if not isinstance(payload, Mapping):
            raise CodeEmbeddingProtocolError("embedding response must be an object")
        data = payload.get("data")
        if not isinstance(data, list) or len(data) != 1:
            raise CodeEmbeddingProtocolError(
                "embedding response must contain exactly one data item"
            )
        item = data[0]
        if not isinstance(item, Mapping) or item.get("index") != 0:
            raise CodeEmbeddingProtocolError("embedding response index must be 0")
        values = item.get("embedding")
        if not isinstance(values, list):
            raise CodeEmbeddingProtocolError("embedding item must contain a list vector")
        try:
            converted = tuple(float(value) for value in values)
            return CodeEmbeddingVector(task=task, role=role, values=converted)
        except (TypeError, ValueError) as exc:
            raise CodeEmbeddingValidationError(str(exc)) from exc

    def _validate_vector(self, vector: CodeEmbeddingVector) -> None:
        if abs(vector.norm - CODE_EMBEDDING_NORM_TARGET) > CODE_EMBEDDING_NORM_TOLERANCE:
            raise CodeEmbeddingValidationError(
                "embedding is not unit normalized within tolerance"
            )

    def embed_query(
        self,
        task: CodeRetrievalTask,
        text: str,
    ) -> CodeEmbeddingVector:
        return self._request_one(text, task=task, role=CodeEmbeddingRole.QUERY)

    def embed_passage(
        self,
        task: CodeRetrievalTask,
        text: str,
    ) -> CodeEmbeddingVector:
        return self._request_one(text, task=task, role=CodeEmbeddingRole.PASSAGE)

    def embed_passages(
        self,
        task: CodeRetrievalTask,
        texts: Iterable[str],
    ) -> Tuple[CodeEmbeddingVector, ...]:
        return tuple(self.embed_passage(task, text) for text in tuple(texts))

    def embed_code_chunks(
        self,
        chunks: Iterable[Chunk],
        *,
        task: CodeRetrievalTask = CodeRetrievalTask.NL2CODE,
    ) -> Tuple[CodeChunkEmbedding, ...]:
        if task not in CODE_CORPUS_TASKS:
            raise CodeEmbeddingValidationError(
                "code corpus chunks require NL2CODE or CODE2CODE passage semantics"
            )
        results: List[CodeChunkEmbedding] = []
        for chunk in chunks:
            if not isinstance(chunk, Chunk):
                raise ValueError("chunks must contain only Chunk values")
            if chunk.metadata.source_type is not SourceType.CODE:
                raise CodeEmbeddingValidationError(
                    "chunk source_type is outside the code-model corpus"
                )
            vector = self.embed_passage(task, chunk.content)
            results.append(
                CodeChunkEmbedding(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    metadata=chunk.metadata,
                    task=task,
                    embedding=vector,
                )
            )
        return tuple(results)
