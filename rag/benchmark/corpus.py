"""Build a temporary lexical benchmark corpus using production RAG chunkers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3
from typing import Iterable, Tuple

from rag.chunking import chunk_markdown, chunk_text_log, safe_chunk_code
from rag.chunking.provenance import source_sha256
from rag.contracts import SearchQuery, SourceType
from rag.index.fts5 import initialize_fts5
from rag.index.lexical_ranking import search_lexical_ranked
from rag.index.sqlite_schema import connect_rag_index
from rag.index.vector_ids import deterministic_chunk_id, deterministic_document_id
from rag.runtime.index_request import RagIndexScope, plan_rag_index


DEFAULT_BENCHMARK_PATHS = (
    "rag",
    "author_mcp",
    "docs",
)


@dataclass(frozen=True)
class BenchmarkCorpusStats:
    documents: int
    chunks: int
    denied: int
    unsupported: int


def _source_type(path: str, *, code_eligible: bool) -> SourceType:
    if code_eligible:
        return SourceType.CODE
    if Path(path).suffix.lower() in {".log", ".txt"}:
        return SourceType.LOG
    return SourceType.DOCUMENTATION


def _drafts_for(path: str, text: str, *, code_eligible: bool):
    if code_eligible:
        result = safe_chunk_code(text, path=path)
        return (
            result.structural_chunks
            if result.structural_chunks
            else result.fallback_chunks
        )
    if Path(path).suffix.lower() == ".md":
        return chunk_markdown(text)
    return chunk_text_log(text)


def build_lexical_benchmark_index(
    project_root: str | Path,
    database_path: str | Path,
    *,
    project_id: str = "codebridge",
    paths: Iterable[str] = DEFAULT_BENCHMARK_PATHS,
) -> BenchmarkCorpusStats:
    root = Path(project_root).resolve()
    plan = plan_rag_index(
        project_id,
        root,
        scope=RagIndexScope.BOTH,
        paths=tuple(paths),
    )
    connection = connect_rag_index(database_path)

    document_count = 0
    chunk_count = 0

    try:
        for candidate in plan.candidates:
            absolute = root / candidate.path
            text = absolute.read_text(encoding="utf-8", errors="replace")
            source_type = _source_type(
                candidate.path,
                code_eligible=candidate.code_eligible,
            )
            document_id = deterministic_document_id(
                project_id,
                source_type,
                candidate.path,
            )
            sha = source_sha256(text)

            connection.execute(
                """
                INSERT OR REPLACE INTO rag_documents (
                    document_id,
                    project_id,
                    source_type,
                    content,
                    path,
                    sha256
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    document_id,
                    project_id,
                    source_type.value,
                    text,
                    candidate.path,
                    sha,
                ),
            )
            document_count += 1

            drafts = _drafts_for(
                candidate.path,
                text,
                code_eligible=candidate.code_eligible,
            )
            for draft in drafts:
                chunk_id = deterministic_chunk_id(
                    document_id,
                    int(draft.ordinal),
                    draft.content,
                )
                heading_path = getattr(draft, "heading_path", None)
                chunk_kind = getattr(draft, "kind", None)
                connection.execute(
                    """
                    INSERT OR REPLACE INTO rag_chunks (
                        chunk_id,
                        document_id,
                        project_id,
                        ordinal,
                        content,
                        source_type,
                        path,
                        line_start,
                        line_end,
                        sha256,
                        heading_path,
                        chunk_kind
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chunk_id,
                        document_id,
                        project_id,
                        int(draft.ordinal),
                        draft.content,
                        source_type.value,
                        candidate.path,
                        getattr(draft, "line_start", None),
                        getattr(draft, "line_end", None),
                        sha,
                        (
                            " > ".join(heading_path)
                            if heading_path
                            else None
                        ),
                        (
                            chunk_kind.value
                            if hasattr(chunk_kind, "value")
                            else (
                                str(chunk_kind)
                                if chunk_kind is not None
                                else None
                            )
                        ),
                    ),
                )
                chunk_count += 1

        connection.commit()
        initialize_fts5(connection, rebuild=True)
        connection.commit()
    finally:
        connection.close()

    return BenchmarkCorpusStats(
        documents=document_count,
        chunks=chunk_count,
        denied=plan.denied_count,
        unsupported=plan.unsupported_count,
    )


def lexical_ranked_paths(
    connection: sqlite3.Connection,
    query_text: str,
    *,
    project_id: str = "codebridge",
    top_k: int = 10,
) -> Tuple[str, ...]:
    results = search_lexical_ranked(
        connection,
        SearchQuery(
            query=query_text,
            project_id=project_id,
            top_k=top_k,
        ),
    )
    seen = set()
    paths = []
    for result in results:
        path = result.metadata.path
        if path and path not in seen:
            seen.add(path)
            paths.append(path)
    return tuple(paths)
