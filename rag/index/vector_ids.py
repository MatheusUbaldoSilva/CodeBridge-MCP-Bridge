"""Deterministic identities and idempotent vector upserts — RAG-009-D."""

from __future__ import annotations

import hashlib
import json
from pathlib import PurePosixPath
from typing import Any, Mapping, Sequence
import uuid

from rag.contracts import SourceType
from rag.models.code_embedding import CODE_EMBEDDING_DIMENSION
from rag.models.embedding import TEXT_EMBEDDING_DIMENSION

from .qdrant_local import CODE_VECTOR_COLLECTION, TEXT_VECTOR_COLLECTION
from .vector_namespace import (
    require_project_namespace,
    vector_payload_with_namespace,
)


VECTOR_ID_NAMESPACE = uuid.uuid5(
    uuid.NAMESPACE_URL,
    "https://codebridge.local/rag/vector-id/v1",
)


def _require_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _canonical_relative_path(path: str) -> str:
    raw = _require_text(path, "path").replace("\\", "/")
    while raw.startswith("./"):
        raw = raw[2:]
    candidate = PurePosixPath(raw)
    if candidate.is_absolute():
        raise ValueError("path must be relative")
    parts = tuple(part for part in candidate.parts if part != ".")
    if not parts or any(part == ".." for part in parts):
        raise ValueError("path must stay inside the project")
    return "/".join(parts)


def deterministic_document_id(
    project_id: str,
    source_type: SourceType,
    path: str,
) -> str:
    namespace = require_project_namespace(project_id)
    if not isinstance(source_type, SourceType):
        raise ValueError("source_type must be SourceType")
    normalized_path = _canonical_relative_path(path)
    canonical = json.dumps(
        {
            "v": 1,
            "project_namespace": namespace,
            "source_type": source_type.value,
            "path": normalized_path,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"doc:{digest}"


def deterministic_chunk_id(
    document_id: str,
    ordinal: int,
    content: str,
) -> str:
    doc_id = _require_text(document_id, "document_id")
    if not isinstance(ordinal, int) or ordinal < 0:
        raise ValueError("ordinal must be an integer >= 0")
    if not isinstance(content, str) or not content:
        raise ValueError("content must be a non-empty string")
    canonical = json.dumps(
        {
            "v": 1,
            "document_id": doc_id,
            "ordinal": ordinal,
            "content_sha256": hashlib.sha256(
                content.encode("utf-8")
            ).hexdigest(),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"chunk:{digest}"


def deterministic_vector_point_id(
    project_id: str,
    collection_name: str,
    chunk_id: str,
) -> str:
    namespace = require_project_namespace(project_id)
    if collection_name not in {
        TEXT_VECTOR_COLLECTION,
        CODE_VECTOR_COLLECTION,
    }:
        raise ValueError("collection_name must be text or code")
    cid = _require_text(chunk_id, "chunk_id")
    name = (
        f"v1|{namespace}|{collection_name}|{cid}"
    )
    return str(uuid.uuid5(VECTOR_ID_NAMESPACE, name))


def expected_vector_dimension(collection_name: str) -> int:
    if collection_name == TEXT_VECTOR_COLLECTION:
        return TEXT_EMBEDDING_DIMENSION
    if collection_name == CODE_VECTOR_COLLECTION:
        return CODE_EMBEDDING_DIMENSION
    raise ValueError("collection_name must be text or code")


def upsert_vector_chunk(
    client: Any,
    *,
    collection_name: str,
    project_id: str,
    chunk_id: str,
    vector: Sequence[float],
    payload: Mapping[str, Any] | None = None,
) -> str:
    if client is None:
        raise ValueError("client must not be None")

    expected = expected_vector_dimension(collection_name)
    values = tuple(float(item) for item in vector)
    if len(values) != expected:
        raise ValueError(
            f"vector dimension mismatch for {collection_name}: "
            f"expected={expected} actual={len(values)}"
        )

    point_id = deterministic_vector_point_id(
        project_id,
        collection_name,
        chunk_id,
    )
    metadata = vector_payload_with_namespace(
        project_id,
        payload,
    )
    existing_chunk_id = metadata.get("chunk_id")
    if existing_chunk_id is not None and existing_chunk_id != chunk_id:
        raise ValueError("payload chunk_id conflicts with chunk_id")
    metadata["chunk_id"] = chunk_id

    try:
        from qdrant_client import models
    except Exception as exc:
        raise RuntimeError(
            "qdrant-client is required for vector upsert"
        ) from exc

    client.upsert(
        collection_name=collection_name,
        points=[
            models.PointStruct(
                id=point_id,
                vector=list(values),
                payload=metadata,
            )
        ],
    )
    return point_id
