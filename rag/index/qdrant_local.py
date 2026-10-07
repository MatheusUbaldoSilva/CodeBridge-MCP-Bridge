"""Persistent Qdrant Local adapter for CodeBridge RAG — RAG-009-B.

The Qdrant dependency is imported lazily so importing this module does not open
storage or require the optional package to be present.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import sqlite3
from typing import Any, Optional, Tuple

from rag.models.code_embedding import CODE_EMBEDDING_DIMENSION
from rag.models.embedding import TEXT_EMBEDDING_DIMENSION


TEXT_VECTOR_COLLECTION = "text"
CODE_VECTOR_COLLECTION = "code"
QDRANT_DISTANCE = "Cosine"
DEFAULT_QDRANT_LOCAL_SUBDIR = Path("CodeBridge") / "rag" / "qdrant"


class QdrantLocalError(RuntimeError):
    pass


class QdrantLocalDependencyError(QdrantLocalError):
    pass


class QdrantCollectionContractError(QdrantLocalError):
    pass


@dataclass(frozen=True)
class VectorCollectionSpec:
    name: str
    dimension: int
    distance: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("collection name must be non-empty")
        if self.dimension < 1:
            raise ValueError("collection dimension must be >= 1")
        if self.distance != QDRANT_DISTANCE:
            raise ValueError("RAG-009-B currently requires Cosine distance")


VECTOR_COLLECTION_SPECS: Tuple[VectorCollectionSpec, ...] = (
    VectorCollectionSpec(
        name=TEXT_VECTOR_COLLECTION,
        dimension=TEXT_EMBEDDING_DIMENSION,
        distance=QDRANT_DISTANCE,
    ),
    VectorCollectionSpec(
        name=CODE_VECTOR_COLLECTION,
        dimension=CODE_EMBEDDING_DIMENSION,
        distance=QDRANT_DISTANCE,
    ),
)


def resolve_qdrant_local_path(
    base_dir: Optional[Path] = None,
) -> Path:
    if base_dir is not None:
        path = Path(base_dir)
        if not str(path):
            raise ValueError("base_dir must not be empty")
        return path

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        root = Path(local_app_data)
    else:
        root = Path.home() / ".local" / "share"

    return root / DEFAULT_QDRANT_LOCAL_SUBDIR


def _prepare_qdrant_sqlite_runtime() -> None:
    """Mirror Qdrant's SQLite thread probe but explicitly close the probe DB.

    qdrant-client 1.19.1 uses a sqlite3 context manager for its first
    CHECK_SAME_THREAD probe. Python's sqlite3 context manager commits or rolls
    back but does not close the connection, which emits ResourceWarning on
    Python 3.13 when that temporary connection is collected. Pre-populating
    the class setting here preserves Qdrant's logic and closes the probe
    explicitly.
    """

    try:
        from qdrant_client.local.persistence import CollectionPersistence
    except Exception as exc:
        raise QdrantLocalDependencyError(
            "qdrant-client local persistence is unavailable"
        ) from exc

    if CollectionPersistence.CHECK_SAME_THREAD is not None:
        return

    connection = sqlite3.connect(":memory:")
    try:
        row = connection.execute(
            "select * from pragma_compile_options "
            "where compile_options like 'THREADSAFE=%'"
        ).fetchone()
        if row is None:
            raise QdrantLocalError(
                "SQLite THREADSAFE compile option is unavailable"
            )
        CollectionPersistence.CHECK_SAME_THREAD = row[0] != "THREADSAFE=1"
    finally:
        connection.close()


def open_qdrant_local(
    path: Optional[Path] = None,
) -> Any:
    selected = resolve_qdrant_local_path(path)

    try:
        from qdrant_client import QdrantClient
    except Exception as exc:
        raise QdrantLocalDependencyError(
            "qdrant-client is required for RAG vector storage"
        ) from exc

    _prepare_qdrant_sqlite_runtime()
    selected.parent.mkdir(parents=True, exist_ok=True)

    try:
        return QdrantClient(path=str(selected))
    except Exception as exc:
        raise QdrantLocalError(
            f"failed to open Qdrant Local storage at {selected}"
        ) from exc


def ensure_vector_collections(
    client: Any,
) -> Tuple[VectorCollectionSpec, ...]:
    if client is None:
        raise ValueError("client must not be None")

    try:
        from qdrant_client import models
    except Exception as exc:
        raise QdrantLocalDependencyError(
            "qdrant-client models are unavailable"
        ) from exc

    for spec in VECTOR_COLLECTION_SPECS:
        try:
            exists = bool(client.collection_exists(spec.name))
        except Exception as exc:
            raise QdrantLocalError(
                f"failed to check collection {spec.name}"
            ) from exc

        if not exists:
            try:
                client.create_collection(
                    collection_name=spec.name,
                    vectors_config=models.VectorParams(
                        size=spec.dimension,
                        distance=models.Distance.COSINE,
                    ),
                )
            except Exception as exc:
                raise QdrantLocalError(
                    f"failed to create collection {spec.name}"
                ) from exc

        _verify_collection_contract(client, spec)

    return VECTOR_COLLECTION_SPECS


def _verify_collection_contract(
    client: Any,
    spec: VectorCollectionSpec,
) -> None:
    try:
        info = client.get_collection(spec.name)
        vectors = info.config.params.vectors
    except Exception as exc:
        raise QdrantLocalError(
            f"failed to inspect collection {spec.name}"
        ) from exc

    if isinstance(vectors, dict):
        raise QdrantCollectionContractError(
            f"collection {spec.name} must use one unnamed dense vector"
        )

    actual_size = int(vectors.size)
    actual_distance = str(vectors.distance)

    if actual_size != spec.dimension:
        raise QdrantCollectionContractError(
            f"collection {spec.name} dimension mismatch: "
            f"expected={spec.dimension} actual={actual_size}"
        )

    if actual_distance != spec.distance:
        raise QdrantCollectionContractError(
            f"collection {spec.name} distance mismatch: "
            f"expected={spec.distance} actual={actual_distance}"
        )


def close_qdrant_local(client: Any) -> None:
    if client is None:
        return

    close = getattr(client, "close", None)
    if not callable(close):
        raise QdrantLocalError("Qdrant client does not expose close()")

    try:
        close()
    except Exception as exc:
        raise QdrantLocalError("failed to close Qdrant Local client") from exc
