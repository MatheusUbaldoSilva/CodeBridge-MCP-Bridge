"""Persistent restart canary for RAG-016-B."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import sqlite3
from typing import Tuple

from rag.benchmark.corpus import build_lexical_benchmark_index
from rag.contracts import SearchQuery
from rag.index.qdrant_local import (
    CODE_VECTOR_COLLECTION,
    TEXT_VECTOR_COLLECTION,
    close_qdrant_local,
    ensure_vector_collections,
    open_qdrant_local,
)
from rag.index.vector_ids import upsert_vector_chunk
from rag.index.vector_namespace import build_project_namespace_filter
from rag.models.code_embedding import CODE_EMBEDDING_DIMENSION
from rag.models.embedding import TEXT_EMBEDDING_DIMENSION
from rag.ranking.dedup import deduplicate_ranked_results
from rag.ranking.rrf import reciprocal_rank_fusion
from rag.retrieval.hybrid_query import collect_hybrid_query_candidates
from rag.runtime.query_classifier import QueryRoute


_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")
RESTART_BASELINE_FILENAME = "restart-baseline.json"


@dataclass(frozen=True)
class RestartProbe:
    project_id: str
    documents: int
    chunks: int
    text_vector_points: int
    code_vector_points: int
    query_text: str
    signature: Tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "project_id": self.project_id,
            "documents": self.documents,
            "chunks": self.chunks,
            "text_vector_points": self.text_vector_points,
            "code_vector_points": self.code_vector_points,
            "query_text": self.query_text,
            "signature": list(self.signature),
        }

    @classmethod
    def from_dict(cls, data: object) -> "RestartProbe":
        if not isinstance(data, dict):
            raise ValueError("restart probe payload must be an object")
        return cls(
            project_id=str(data["project_id"]),
            documents=int(data["documents"]),
            chunks=int(data["chunks"]),
            text_vector_points=int(data["text_vector_points"]),
            code_vector_points=int(data["code_vector_points"]),
            query_text=str(data["query_text"]),
            signature=tuple(str(item) for item in data["signature"]),
        )


def _basis(dimension: int) -> list[float]:
    return [1.0] + [0.0] * (dimension - 1)


def _rows(connection: sqlite3.Connection):
    text_row = connection.execute(
        """
        SELECT chunk_id, document_id, content, source_type, path,
               line_start, line_end, sha256
        FROM rag_chunks
        WHERE source_type != 'CODE'
        ORDER BY document_id, ordinal, chunk_id
        LIMIT 1
        """
    ).fetchone()
    code_row = connection.execute(
        """
        SELECT chunk_id, document_id, content, source_type, path,
               line_start, line_end, sha256
        FROM rag_chunks
        WHERE source_type = 'CODE'
        ORDER BY document_id, ordinal, chunk_id
        LIMIT 1
        """
    ).fetchone()
    if text_row is None or code_row is None:
        raise RuntimeError("restart canary requires text and code chunks")
    return text_row, code_row


def _payload(row) -> dict[str, object]:
    return {
        "document_id": str(row[1]),
        "content": str(row[2]),
        "source_type": str(row[3]),
        "path": row[4],
        "line_start": row[5],
        "line_end": row[6],
        "sha256": row[7],
    }


def _query_text(content: str) -> str:
    tokens = _TOKEN_RE.findall(content)
    if not tokens:
        raise RuntimeError("restart canary text chunk has no searchable tokens")
    return " ".join(tokens[: min(3, len(tokens))])


def _count_vectors(client, collection: str, project_id: str) -> int:
    result = client.count(
        collection_name=collection,
        count_filter=build_project_namespace_filter(project_id),
        exact=True,
    )
    return int(result.count)


def _signature(
    connection: sqlite3.Connection,
    qdrant,
    *,
    project_id: str,
    query_text: str,
) -> Tuple[str, ...]:
    candidates = collect_hybrid_query_candidates(
        connection,
        qdrant,
        SearchQuery(
            query=query_text,
            project_id=project_id,
            top_k=10,
        ),
        route=QueryRoute.HYBRID,
        text_query_vector=_basis(TEXT_EMBEDDING_DIMENSION),
        code_query_vector=_basis(CODE_EMBEDDING_DIMENSION),
    )
    fused = reciprocal_rank_fusion(
        (
            candidates.lexical,
            candidates.text_vector,
            candidates.code_vector,
        ),
        top_k=20,
    )
    return tuple(
        item.chunk_id
        for item in deduplicate_ranked_results(
            fused,
            top_k=10,
        ).results
    )


def prepare_restart_probe(
    project_root: str | Path,
    state_directory: str | Path,
    *,
    project_id: str = "codebridge",
    paths: tuple[str, ...] = ("rag", "author_mcp", "docs"),
) -> RestartProbe:
    root = Path(project_root).resolve()
    state = Path(state_directory).resolve()
    state.mkdir(parents=True, exist_ok=True)

    sqlite_path = state / "restart.sqlite3"
    qdrant_path = state / "qdrant"

    stats = build_lexical_benchmark_index(
        root,
        sqlite_path,
        project_id=project_id,
        paths=paths,
    )

    connection = sqlite3.connect(str(sqlite_path))
    qdrant = open_qdrant_local(qdrant_path)
    try:
        ensure_vector_collections(qdrant)
        text_row, code_row = _rows(connection)

        upsert_vector_chunk(
            qdrant,
            collection_name=TEXT_VECTOR_COLLECTION,
            project_id=project_id,
            chunk_id=str(text_row[0]),
            vector=_basis(TEXT_EMBEDDING_DIMENSION),
            payload=_payload(text_row),
        )
        upsert_vector_chunk(
            qdrant,
            collection_name=CODE_VECTOR_COLLECTION,
            project_id=project_id,
            chunk_id=str(code_row[0]),
            vector=_basis(CODE_EMBEDDING_DIMENSION),
            payload=_payload(code_row),
        )

        query = _query_text(str(text_row[2]))
        signature = _signature(
            connection,
            qdrant,
            project_id=project_id,
            query_text=query,
        )
        probe = RestartProbe(
            project_id=project_id,
            documents=stats.documents,
            chunks=stats.chunks,
            text_vector_points=_count_vectors(
                qdrant,
                TEXT_VECTOR_COLLECTION,
                project_id,
            ),
            code_vector_points=_count_vectors(
                qdrant,
                CODE_VECTOR_COLLECTION,
                project_id,
            ),
            query_text=query,
            signature=signature,
        )
    finally:
        connection.close()
        close_qdrant_local(qdrant)

    (state / RESTART_BASELINE_FILENAME).write_text(
        json.dumps(
            probe.to_dict(),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return probe


def verify_restart_probe(
    state_directory: str | Path,
) -> RestartProbe:
    state = Path(state_directory).resolve()
    baseline_path = state / RESTART_BASELINE_FILENAME
    if not baseline_path.is_file():
        raise FileNotFoundError(
            f"restart baseline not found: {baseline_path}"
        )

    baseline = RestartProbe.from_dict(
        json.loads(baseline_path.read_text(encoding="utf-8"))
    )
    sqlite_path = state / "restart.sqlite3"
    qdrant_path = state / "qdrant"

    connection = sqlite3.connect(str(sqlite_path))
    qdrant = open_qdrant_local(qdrant_path)
    try:
        documents = int(
            connection.execute(
                "SELECT COUNT(*) FROM rag_documents WHERE project_id = ?",
                (baseline.project_id,),
            ).fetchone()[0]
        )
        chunks = int(
            connection.execute(
                "SELECT COUNT(*) FROM rag_chunks WHERE project_id = ?",
                (baseline.project_id,),
            ).fetchone()[0]
        )
        observed = RestartProbe(
            project_id=baseline.project_id,
            documents=documents,
            chunks=chunks,
            text_vector_points=_count_vectors(
                qdrant,
                TEXT_VECTOR_COLLECTION,
                baseline.project_id,
            ),
            code_vector_points=_count_vectors(
                qdrant,
                CODE_VECTOR_COLLECTION,
                baseline.project_id,
            ),
            query_text=baseline.query_text,
            signature=_signature(
                connection,
                qdrant,
                project_id=baseline.project_id,
                query_text=baseline.query_text,
            ),
        )
    finally:
        connection.close()
        close_qdrant_local(qdrant)

    if observed != baseline:
        raise RuntimeError(
            "restart recovery mismatch: "
            f"expected={baseline.to_dict()} observed={observed.to_dict()}"
        )
    return observed
