"""Lazy bridge between the MCP surface and the optional RAG package.

This module is intentionally separate from mcp_server so the critical MCP
execution surface keeps importing even when the RAG package is unavailable.
"""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any, Callable, Optional


ROOT = Path(__file__).resolve().parent.parent


_RAG_INDEX_EXECUTOR: Optional[Callable[[Any], dict[str, object]]] = None
_RAG_SEARCH_EXECUTOR: Optional[Callable[[Any, Any], tuple[Any, ...]]] = None


def register_rag_index_executor(
    executor: Optional[Callable[[Any], dict[str, object]]],
) -> None:
    global _RAG_INDEX_EXECUTOR
    if executor is not None and not callable(executor):
        raise ValueError("executor must be callable or None")
    _RAG_INDEX_EXECUTOR = executor


def register_rag_search_executor(
    executor: Optional[Callable[[Any, Any], tuple[Any, ...]]],
) -> None:
    global _RAG_SEARCH_EXECUTOR
    if executor is not None and not callable(executor):
        raise ValueError("executor must be callable or None")
    _RAG_SEARCH_EXECUTOR = executor


def _ensure_project_root() -> None:
    value = str(ROOT)
    if value not in sys.path:
        sys.path.insert(0, value)


def get_rag_status() -> dict[str, Any]:
    _ensure_project_root()

    from rag.runtime.status import build_rag_status

    return build_rag_status().to_dict()


def index_rag(
    *,
    project_id: str,
    project_root: str,
    scope: str = "BOTH",
    paths: Optional[list[str]] = None,
    execute: bool = False,
) -> dict[str, Any]:
    _ensure_project_root()

    from rag.runtime.index_request import (
        RagIndexScope,
        run_explicit_rag_index,
    )

    result = run_explicit_rag_index(
        project_id,
        project_root,
        scope=RagIndexScope(scope),
        paths=tuple(paths or ()),
        execute=bool(execute),
        executor=_RAG_INDEX_EXECUTOR,
    )
    return result.to_dict()


def search_rag_context(
    *,
    query: str,
    project_id: str,
    source_types: Optional[list[str]] = None,
    top_k: int = 10,
    path_filter: Optional[str] = None,
    branch: Optional[str] = None,
) -> dict[str, Any]:
    _ensure_project_root()

    from rag.runtime.search_service import search_context

    result = search_context(
        query=query,
        project_id=project_id,
        source_types=tuple(source_types or ()),
        top_k=top_k,
        path_filter=path_filter,
        branch=branch,
        semantic_executor=_RAG_SEARCH_EXECUTOR,
    )
    return result.to_dict()


def get_rag_context(
    *,
    project_id: str,
    chunk_ids: list[str],
    include_document_content: bool = False,
) -> dict[str, Any]:
    _ensure_project_root()

    from rag.runtime.context_service import get_context

    result = get_context(
        project_id=project_id,
        chunk_ids=tuple(chunk_ids),
        include_document_content=include_document_content,
    )
    return result.to_dict()
