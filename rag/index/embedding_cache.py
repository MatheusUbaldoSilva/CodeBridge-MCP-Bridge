"""Persistent exact-key cache for text embeddings — RAG-006-E.

This is a cache only, not a vector index.
Importing this module does not create or open a database.
"""

from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path
import sqlite3
import struct
from typing import Optional, Sequence, Tuple, Union


TEXT_EMBEDDING_CACHE_SCHEMA_VERSION = 1
DEFAULT_TEXT_EMBEDDING_CACHE_FILENAME = "text_embedding_cache.sqlite3"
TEXT_EMBEDDING_CACHE_TABLE = "rag_text_embedding_cache"


class TextEmbeddingCacheError(RuntimeError):
    pass


class TextEmbeddingCacheVersionError(TextEmbeddingCacheError):
    pass


class TextEmbeddingCacheIntegrityError(TextEmbeddingCacheError):
    pass


_SCHEMA_SQL = f"""
CREATE TABLE IF NOT EXISTS {TEXT_EMBEDDING_CACHE_TABLE} (
    namespace TEXT NOT NULL
        CHECK (length(trim(namespace)) > 0),
    chunk_sha256 TEXT NOT NULL
        CHECK (length(chunk_sha256) = 64),
    dimension INTEGER NOT NULL
        CHECK (dimension > 0),
    vector_blob BLOB NOT NULL,
    vector_sha256 TEXT NOT NULL
        CHECK (length(vector_sha256) = 64),
    PRIMARY KEY (namespace, chunk_sha256)
);

CREATE INDEX IF NOT EXISTS idx_rag_text_embedding_cache_namespace
    ON {TEXT_EMBEDDING_CACHE_TABLE}(namespace);
"""


def _require_connection(connection: sqlite3.Connection) -> None:
    if not isinstance(connection, sqlite3.Connection):
        raise ValueError("connection must be sqlite3.Connection")


def _require_sha256(value: str, field_name: str) -> str:
    normalized = str(value or "").lower()
    if (
        len(normalized) != 64
        or any(
            char not in "0123456789abcdef"
            for char in normalized
        )
    ):
        raise ValueError(
            f"{field_name} must be exactly 64 hexadecimal characters"
        )
    return normalized


def _require_namespace(value: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError("namespace must be non-empty")
    return normalized


def _encode_vector(values: Sequence[float]) -> bytes:
    if not values:
        raise ValueError("embedding vector must be non-empty")

    converted = tuple(float(value) for value in values)
    if any(
        not math.isfinite(value)
        for value in converted
    ):
        raise ValueError(
            "embedding vector must contain only finite values"
        )

    return struct.pack(
        f"<{len(converted)}d",
        *converted,
    )


def _decode_vector(
    blob: bytes,
    *,
    dimension: int,
) -> Tuple[float, ...]:
    if dimension < 1:
        raise ValueError("dimension must be >= 1")

    expected_bytes = dimension * 8
    if len(blob) != expected_bytes:
        raise TextEmbeddingCacheIntegrityError(
            "cached vector byte length does not match dimension"
        )

    return tuple(
        struct.unpack(
            f"<{dimension}d",
            blob,
        )
    )


def initialize_text_embedding_cache(
    connection: sqlite3.Connection,
) -> int:
    _require_connection(connection)

    row = connection.execute(
        "PRAGMA user_version"
    ).fetchone()
    version = int(row[0])

    if version not in (
        0,
        TEXT_EMBEDDING_CACHE_SCHEMA_VERSION,
    ):
        raise TextEmbeddingCacheVersionError(
            "unsupported text embedding cache schema "
            f"version {version}"
        )

    if version == 0:
        connection.executescript(_SCHEMA_SQL)
        connection.execute(
            "PRAGMA user_version = "
            f"{TEXT_EMBEDDING_CACHE_SCHEMA_VERSION}"
        )
        connection.commit()

    table = connection.execute(
        """
        SELECT sql
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        """,
        (TEXT_EMBEDDING_CACHE_TABLE,),
    ).fetchone()
    if not table:
        raise TextEmbeddingCacheIntegrityError(
            "text embedding cache table is missing"
        )

    return TEXT_EMBEDDING_CACHE_SCHEMA_VERSION


def resolve_text_embedding_cache_path(
    *,
    local_app_data: Optional[Path] = None,
) -> Path:
    root = local_app_data
    if root is None:
        value = os.environ.get("LOCALAPPDATA")
        if not value:
            raise RuntimeError(
                "LOCALAPPDATA is required to resolve cache path"
            )
        root = Path(value)

    return (
        Path(root)
        / "CodeBridge"
        / "cache"
        / "rag"
        / DEFAULT_TEXT_EMBEDDING_CACHE_FILENAME
    )


def connect_text_embedding_cache(
    database: Union[str, Path],
) -> sqlite3.Connection:
    value = str(database).strip()
    if not value:
        raise ValueError("database path must be non-empty")

    connection = sqlite3.connect(value)
    try:
        connection.execute(
            "PRAGMA busy_timeout = 5000"
        )
        initialize_text_embedding_cache(
            connection
        )
    except Exception:
        connection.close()
        raise

    return connection


class TextEmbeddingCache:
    def __init__(
        self,
        connection: sqlite3.Connection,
    ) -> None:
        _require_connection(connection)
        initialize_text_embedding_cache(
            connection
        )
        self._connection = connection

    def get(
        self,
        *,
        namespace: str,
        chunk_sha256: str,
        dimension: int,
    ) -> Optional[Tuple[float, ...]]:
        normalized_namespace = _require_namespace(
            namespace
        )
        normalized_chunk_sha = _require_sha256(
            chunk_sha256,
            "chunk_sha256",
        )
        if dimension < 1:
            raise ValueError(
                "dimension must be >= 1"
            )

        row = self._connection.execute(
            f"""
            SELECT
                dimension,
                vector_blob,
                vector_sha256
            FROM {TEXT_EMBEDDING_CACHE_TABLE}
            WHERE namespace = ?
              AND chunk_sha256 = ?
            """,
            (
                normalized_namespace,
                normalized_chunk_sha,
            ),
        ).fetchone()

        if row is None:
            return None

        stored_dimension = int(row[0])
        if stored_dimension != dimension:
            raise TextEmbeddingCacheIntegrityError(
                "cached vector dimension does not match requested dimension"
            )

        blob = bytes(row[1])
        stored_vector_sha = _require_sha256(
            str(row[2]),
            "vector_sha256",
        )
        actual_vector_sha = hashlib.sha256(
            blob
        ).hexdigest()
        if actual_vector_sha != stored_vector_sha:
            raise TextEmbeddingCacheIntegrityError(
                "cached vector SHA-256 verification failed"
            )

        return _decode_vector(
            blob,
            dimension=dimension,
        )

    def put(
        self,
        *,
        namespace: str,
        chunk_sha256: str,
        dimension: int,
        values: Sequence[float],
    ) -> None:
        normalized_namespace = _require_namespace(
            namespace
        )
        normalized_chunk_sha = _require_sha256(
            chunk_sha256,
            "chunk_sha256",
        )
        if dimension < 1:
            raise ValueError(
                "dimension must be >= 1"
            )
        if len(values) != dimension:
            raise ValueError(
                "embedding vector length must match dimension"
            )

        blob = _encode_vector(values)
        vector_sha = hashlib.sha256(
            blob
        ).hexdigest()

        self._connection.execute(
            f"""
            INSERT INTO {TEXT_EMBEDDING_CACHE_TABLE} (
                namespace,
                chunk_sha256,
                dimension,
                vector_blob,
                vector_sha256
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(namespace, chunk_sha256)
            DO UPDATE SET
                dimension = excluded.dimension,
                vector_blob = excluded.vector_blob,
                vector_sha256 = excluded.vector_sha256
            """,
            (
                normalized_namespace,
                normalized_chunk_sha,
                dimension,
                sqlite3.Binary(blob),
                vector_sha,
            ),
        )
        self._connection.commit()

    def count(
        self,
        *,
        namespace: Optional[str] = None,
    ) -> int:
        if namespace is None:
            row = self._connection.execute(
                f"""
                SELECT count(*)
                FROM {TEXT_EMBEDDING_CACHE_TABLE}
                """
            ).fetchone()
        else:
            normalized_namespace = _require_namespace(
                namespace
            )
            row = self._connection.execute(
                f"""
                SELECT count(*)
                FROM {TEXT_EMBEDDING_CACHE_TABLE}
                WHERE namespace = ?
                """,
                (normalized_namespace,),
            ).fetchone()

        return int(row[0])

    def delete_namespace(
        self,
        namespace: str,
    ) -> int:
        normalized_namespace = _require_namespace(
            namespace
        )
        cursor = self._connection.execute(
            f"""
            DELETE FROM {TEXT_EMBEDDING_CACHE_TABLE}
            WHERE namespace = ?
            """,
            (normalized_namespace,),
        )
        self._connection.commit()
        return int(cursor.rowcount)
