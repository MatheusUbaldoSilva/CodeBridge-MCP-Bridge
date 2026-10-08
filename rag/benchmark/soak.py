"""Repeated storage/retrieval soak harness for RAG-016-A."""

from __future__ import annotations

from dataclasses import dataclass
import gc
from pathlib import Path
import re
import sqlite3
import tempfile
import time
from typing import Iterable, Optional, Tuple

from rag.benchmark.corpus import build_lexical_benchmark_index
from rag.benchmark.metrics import (
    current_process_rss_bytes,
    directory_size_bytes,
)
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


@dataclass(frozen=True)
class SoakResult:
    project_id: str
    index_cycles: int
    query_cycles: int
    documents: int
    chunks: int
    text_vector_points: int
    code_vector_points: int
    stable_signature: Tuple[str, ...]
    elapsed_seconds: float
    rss_start_bytes: int
    rss_end_bytes: int
    rss_delta_bytes: int
    sqlite_size_bytes: int
    qdrant_size_bytes: int
    total_index_size_bytes: int

    def to_dict(self) -> dict[str, object]:
        return {
            "project_id": self.project_id,
            "index_cycles": self.index_cycles,
            "query_cycles": self.query_cycles,
            "documents": self.documents,
            "chunks": self.chunks,
            "text_vector_points": self.text_vector_points,
            "code_vector_points": self.code_vector_points,
            "stable_signature": list(self.stable_signature),
            "elapsed_seconds": self.elapsed_seconds,
            "rss_start_bytes": self.rss_start_bytes,
            "rss_end_bytes": self.rss_end_bytes,
            "rss_delta_bytes": self.rss_delta_bytes,
            "sqlite_size_bytes": self.sqlite_size_bytes,
            "qdrant_size_bytes": self.qdrant_size_bytes,
            "total_index_size_bytes": self.total_index_size_bytes,
        }


def _basis(dimension: int) -> list[float]:
    return [1.0] + [0.0] * (dimension - 1)


def _first_rows(
    connection: sqlite3.Connection,
) -> tuple[tuple[object, ...], tuple[object, ...]]:
    text_row = connection.execute(
        """
        SELECT
            chunk_id,
            document_id,
            content,
            source_type,
            path,
            line_start,
            line_end,
            sha256
        FROM rag_chunks
        WHERE source_type != 'CODE'
        ORDER BY document_id, ordinal, chunk_id
        LIMIT 1
        """
    ).fetchone()
    code_row = connection.execute(
        """
        SELECT
            chunk_id,
            document_id,
            content,
            source_type,
            path,
            line_start,
            line_end,
            sha256
        FROM rag_chunks
        WHERE source_type = 'CODE'
        ORDER BY document_id, ordinal, chunk_id
        LIMIT 1
        """
    ).fetchone()
    if text_row is None:
        raise RuntimeError("soak corpus requires at least one text chunk")
    if code_row is None:
        raise RuntimeError("soak corpus requires at least one code chunk")
    return text_row, code_row


def _payload(row: tuple[object, ...]) -> dict[str, object]:
    return {
        "document_id": str(row[1]),
        "content": str(row[2]),
        "source_type": str(row[3]),
        "path": row[4],
        "line_start": row[5],
        "line_end": row[6],
        "sha256": row[7],
    }


def _query_from_content(content: str) -> str:
    tokens = _TOKEN_RE.findall(content)
    if not tokens:
        raise RuntimeError("selected text chunk has no searchable tokens")
    return " ".join(tokens[: min(3, len(tokens))])


def _project_vector_count(
    client,
    collection_name: str,
    project_id: str,
) -> int:
    result = client.count(
        collection_name=collection_name,
        count_filter=build_project_namespace_filter(project_id),
        exact=True,
    )
    return int(result.count)


def _sqlite_counts(
    connection: sqlite3.Connection,
    project_id: str,
) -> tuple[int, int]:
    documents = int(
        connection.execute(
            "SELECT COUNT(*) FROM rag_documents WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0]
    )
    chunks = int(
        connection.execute(
            "SELECT COUNT(*) FROM rag_chunks WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0]
    )
    return documents, chunks


def _upsert_probe_vectors(
    qdrant,
    project_id: str,
    text_row: tuple[object, ...],
    code_row: tuple[object, ...],
) -> None:
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


def run_storage_retrieval_soak(
    project_root: str | Path,
    *,
    project_id: str = "codebridge",
    index_cycles: int = 5,
    query_cycles: int = 500,
    paths: Iterable[str] = ("rag", "author_mcp", "docs"),
    working_directory: Optional[str | Path] = None,
) -> SoakResult:
    if not isinstance(index_cycles, int) or index_cycles < 1:
        raise ValueError("index_cycles must be >= 1")
    if not isinstance(query_cycles, int) or query_cycles < 1:
        raise ValueError("query_cycles must be >= 1")

    root = Path(project_root).resolve()
    started = time.perf_counter()
    rss_start = current_process_rss_bytes()

    owned_temp = None
    if working_directory is None:
        owned_temp = tempfile.TemporaryDirectory(
            prefix="codebridge-rag016-soak-"
        )
        work = Path(owned_temp.name)
    else:
        work = Path(working_directory).resolve()
        work.mkdir(parents=True, exist_ok=True)

    db = work / "soak.sqlite3"
    qdrant_path = work / "qdrant"
    qdrant = None
    connection = None

    try:
        expected_counts = None
        query_text = None
        text_row = None
        code_row = None

        for cycle in range(1, index_cycles + 1):
            stats = build_lexical_benchmark_index(
                root,
                db,
                project_id=project_id,
                paths=tuple(paths),
            )

            if connection is not None:
                connection.close()
            connection = sqlite3.connect(str(db))

            counts = _sqlite_counts(connection, project_id)
            if expected_counts is None:
                expected_counts = counts
            elif counts != expected_counts:
                raise RuntimeError(
                    "repeated indexing changed document/chunk counts: "
                    f"expected={expected_counts} actual={counts} "
                    f"cycle={cycle}"
                )

            if counts != (stats.documents, stats.chunks):
                raise RuntimeError(
                    "soak corpus stats disagree with persisted SQLite counts"
                )

            text_row, code_row = _first_rows(connection)
            if query_text is None:
                query_text = _query_from_content(str(text_row[2]))

            if qdrant is None:
                qdrant = open_qdrant_local(qdrant_path)
                ensure_vector_collections(qdrant)

            _upsert_probe_vectors(
                qdrant,
                project_id,
                text_row,
                code_row,
            )

            if (
                _project_vector_count(
                    qdrant,
                    TEXT_VECTOR_COLLECTION,
                    project_id,
                )
                != 1
            ):
                raise RuntimeError(
                    "text-vector idempotence failed during soak"
                )
            if (
                _project_vector_count(
                    qdrant,
                    CODE_VECTOR_COLLECTION,
                    project_id,
                )
                != 1
            ):
                raise RuntimeError(
                    "code-vector idempotence failed during soak"
                )

        assert connection is not None
        assert qdrant is not None
        assert expected_counts is not None
        assert query_text is not None

        stable_signature = None
        text_vector = _basis(TEXT_EMBEDDING_DIMENSION)
        code_vector = _basis(CODE_EMBEDDING_DIMENSION)

        for cycle in range(1, query_cycles + 1):
            candidates = collect_hybrid_query_candidates(
                connection,
                qdrant,
                SearchQuery(
                    query=query_text,
                    project_id=project_id,
                    top_k=10,
                ),
                route=QueryRoute.HYBRID,
                text_query_vector=text_vector,
                code_query_vector=code_vector,
            )
            fused = reciprocal_rank_fusion(
                (
                    candidates.lexical,
                    candidates.text_vector,
                    candidates.code_vector,
                ),
                top_k=20,
            )
            final = deduplicate_ranked_results(
                fused,
                top_k=10,
            ).results
            signature = tuple(item.chunk_id for item in final)

            if not signature:
                raise RuntimeError(
                    f"soak query produced no results at cycle {cycle}"
                )
            if stable_signature is None:
                stable_signature = signature
            elif signature != stable_signature:
                raise RuntimeError(
                    "soak query ranking changed between identical cycles: "
                    f"cycle={cycle}"
                )

        gc.collect()
        rss_end = current_process_rss_bytes()
        sqlite_size = directory_size_bytes(db)
        qdrant_size = directory_size_bytes(qdrant_path)
        elapsed = time.perf_counter() - started

        assert stable_signature is not None
        return SoakResult(
            project_id=project_id,
            index_cycles=index_cycles,
            query_cycles=query_cycles,
            documents=expected_counts[0],
            chunks=expected_counts[1],
            text_vector_points=_project_vector_count(
                qdrant,
                TEXT_VECTOR_COLLECTION,
                project_id,
            ),
            code_vector_points=_project_vector_count(
                qdrant,
                CODE_VECTOR_COLLECTION,
                project_id,
            ),
            stable_signature=stable_signature,
            elapsed_seconds=elapsed,
            rss_start_bytes=rss_start,
            rss_end_bytes=rss_end,
            rss_delta_bytes=rss_end - rss_start,
            sqlite_size_bytes=sqlite_size,
            qdrant_size_bytes=qdrant_size,
            total_index_size_bytes=sqlite_size + qdrant_size,
        )
    finally:
        if connection is not None:
            connection.close()
        if qdrant is not None:
            close_qdrant_local(qdrant)
        if owned_temp is not None:
            owned_temp.cleanup()
