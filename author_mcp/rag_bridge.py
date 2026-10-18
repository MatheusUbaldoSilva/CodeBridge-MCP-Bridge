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


def configure_production_rag_executors(
    *,
    staged_index: bool = False,
    semantic_search: bool = False,
) -> dict[str, bool]:
    """Explicitly register real RAG adapters; no automatic production activation.

    Index execution creates staging only. Promoting persistent data and proving
    READY remains the responsibility of RAG-017-H.
    """
    _ensure_project_root()
    if staged_index:
        from rag.runtime.production_index import build_staged_index
        register_rag_index_executor(build_staged_index)
    if semantic_search:
        from rag.runtime.production_search import search_persistent_semantic
        register_rag_search_executor(search_persistent_semantic)
    return {
        "staged_index_registered": _RAG_INDEX_EXECUTOR is not None,
        "semantic_search_registered": _RAG_SEARCH_EXECUTOR is not None,
    }


_V1_PYTHON: Optional[Path] = None



def _v1_verify_search_sources(payload: dict[str, Any], repository_root: Path) -> dict[str, Any]:
    """Verify search result hashes against the approved live repository."""
    from rag.contracts import SourceMetadata, SourceType
    from rag.sources.staleness import evaluate_source_staleness

    for record in payload.get("results", []):
        metadata = record.get("metadata") or {}
        try:
            source = SourceMetadata(
                project_id=metadata["project_id"],
                source_type=SourceType(metadata["source_type"]),
                path=metadata.get("path"),
                sha256=metadata.get("sha256"),
            )
            if source.project_id != "codebridge":
                raise ValueError("outside approved source project")
            evaluation = evaluate_source_staleness(repository_root, source)
            status, reason, current_sha = (
                evaluation.status.value, evaluation.reason, evaluation.current_sha256
            )
        except (KeyError, TypeError, ValueError, OSError, UnicodeError):
            status, reason, current_sha = ("UNVERIFIED", "SOURCE_VERIFICATION_FAILED", None)
        record["source_verification"] = {
            "status": status, "reason": reason, "current_sha256": current_sha,
        }
        record["stale"] = bool(record.get("stale")) or status != "FRESH"
    # Preserve historical results; prioritize only verified current sources.
    items = payload.get("results", [])
    items.sort(key=lambda item: (item["source_verification"]["status"] != "FRESH", item["rank"]))
    for position, item in enumerate(items, 1):
        item["rank"] = position
    return payload


def _v1_semantic_process_executor(query: Any, route: Any) -> tuple[Any, ...]:
    """Use a trusted, separately configured Python for vector dependencies."""
    import json
    import subprocess
    from rag.contracts import SearchResult, SourceMetadata, SourceType

    if query.project_id != "codebridge":
        raise PermissionError("V1 semantic search project is not approved")
    if _V1_PYTHON is None:
        raise RuntimeError("V1 semantic Python is not configured")
    payload = {
        "query": query.query, "project_id": query.project_id,
        "source_types": [value.value for value in query.source_types],
        "top_k": query.top_k, "path_filter": query.path_filter,
        "branch": query.branch, "route": route.value,
    }
    if not 1 <= query.top_k <= 20:
        raise ValueError("V1 semantic top_k must be between 1 and 20")
    try:
        completed = subprocess.run(
            [str(_V1_PYTHON), "-m", "rag.runtime.v1_semantic_worker"],
            cwd=str(ROOT), input=json.dumps(payload), text=True,
            capture_output=True, timeout=180, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("V1 semantic worker timed out") from exc
    if completed.returncode != 0:
        raise RuntimeError(
            "V1 semantic worker failed: " + completed.stderr[-700:]
        )
    records = json.loads(completed.stdout)
    results = []
    for record in records:
        metadata = dict(record["metadata"])
        metadata["source_type"] = SourceType(metadata["source_type"])
        results.append(SearchResult(
            chunk_id=record["chunk_id"],
            document_id=record["document_id"],
            content=record["content"],
            metadata=SourceMetadata(**metadata),
            score=float(record["score"]),
            rank=int(record["rank"]),
            retrieval_modes=tuple(record.get("retrieval_modes", ())),
            stale=bool(record.get("stale", False)),
        ))
    return tuple(results)


def _configure_v1_semantic_for_project(project_id: str) -> None:
    """Explicit local opt-in; no import of vector libraries in the MCP runtime."""
    import json
    import os

    global _V1_PYTHON
    path = Path(os.environ.get("LOCALAPPDATA") or str(Path.home()))
    path = path / "CodeBridge-MCP-Bridge" / "rag_v1_semantic.json"
    if not path.is_file():
        if _RAG_SEARCH_EXECUTOR is _v1_semantic_process_executor:
            register_rag_search_executor(None)
        _V1_PYTHON = None
        return
    config = json.loads(path.read_text(encoding="utf-8-sig"))
    enabled = config.get("enabled") is True and config.get("project_id") == "codebridge"
    if not enabled or project_id != "codebridge":
        if _RAG_SEARCH_EXECUTOR is _v1_semantic_process_executor:
            register_rag_search_executor(None)
        _V1_PYTHON = None
        return
    executable = Path(config["python_executable"])
    if not executable.is_absolute() or not executable.is_file():
        raise RuntimeError("V1 semantic Python executable is unavailable")
    _V1_PYTHON = executable
    register_rag_search_executor(_v1_semantic_process_executor)


def _ensure_project_root() -> None:
    value = str(ROOT)
    if value not in sys.path:
        sys.path.insert(0, value)


def format_rag_error(exc: BaseException) -> dict[str, Any]:
    _ensure_project_root()
    from rag.runtime.errors import classify_rag_error
    return classify_rag_error(exc).to_dict()


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

    _configure_v1_semantic_for_project(project_id)

    result = search_context(
        query=query,
        project_id=project_id,
        source_types=tuple(source_types or ()),
        top_k=top_k,
        path_filter=path_filter,
        branch=branch,
        semantic_executor=_RAG_SEARCH_EXECUTOR,
    )
    payload = result.to_dict()
    if project_id == "codebridge":
        import json
        import os
        config_path = Path(os.environ.get("LOCALAPPDATA") or str(Path.home())) / "CodeBridge-MCP-Bridge" / "rag_v1_semantic.json"
        if config_path.is_file():
            config = json.loads(config_path.read_text(encoding="utf-8-sig"))
            if config.get("enabled") is True and config.get("project_id") == "codebridge":
                root = Path(config["repository_root"]).resolve()
                if not root.is_dir() or not (root / ".git").exists():
                    raise RuntimeError("approved repository root is invalid")
                return _v1_verify_search_sources(payload, root)
    return payload


def get_rag_context(
    *,
    project_id: str,
    chunk_ids: list[str],
    include_document_content: bool = False,
    project_root: Optional[str] = None,
    allow_stale: bool = False,
) -> dict[str, Any]:
    _ensure_project_root()

    from rag.runtime.context_service import get_context

    result = get_context(
        project_id=project_id,
        chunk_ids=tuple(chunk_ids),
        include_document_content=include_document_content,
        project_root=project_root,
        allow_stale=allow_stale,
    )
    return result.to_dict()
