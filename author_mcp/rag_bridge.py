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
    import time
    from rag.runtime.production_generation_lock import (
        production_generation_lock, ProductionGenerationBusy,
    )
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
    # Qdrant Local is single-process storage and Jina model startup cannot
    # be safely raced across MCP requests. Serialize only vector workers,
    # using a dedicated Win32 cross-process lock. Do NOT use the generation
    # writer lock here: the caller already holds a shared reader pin.
    deadline = time.monotonic() + 100
    while True:
        try:
            with production_generation_lock(exclusive=True, channel="semantic"):
                try:
                    completed = subprocess.run(
                        [str(_V1_PYTHON), "-m", "rag.runtime.v1_semantic_worker"],
                        cwd=str(ROOT), input=json.dumps(payload), text=True,
                        capture_output=True, timeout=180, check=False,
                    )
                except subprocess.TimeoutExpired as exc:
                    raise RuntimeError("V1 semantic worker timed out") from exc
            break
        except ProductionGenerationBusy as exc:
            if time.monotonic() >= deadline:
                raise RuntimeError("V1 semantic worker queue timed out") from exc
            time.sleep(0.2)
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


def inspect_rag_generation_readers() -> dict[str, Any]:
    """Attest loaded MCP reader code and shared lock in the live server.

    Probe is read-only and does NOT authorize an activation. A separate
    successful public CODE semantic query is still required to prove the
    external child worker executes this installed implementation.
    """
    _ensure_project_root()
    import os
    from rag.runtime.production_generation_lock import (
        ProductionGenerationBusy, production_generation_lock,
    )
    from rag.runtime.production_generation_read import production_generation_read

    loaded = {
        "search": "production_generation_read" in search_rag_context.__code__.co_names,
        "context": "production_generation_read" in get_rag_context.__code__.co_names,
        "status": "production_generation_read" in get_rag_status.__code__.co_names,
    }
    # Inspect the *loaded* function bytecode, not the installed .py file:
    # the running MCP server may have imported the previous implementation
    # before a CodeBridge GUI update. This is only a diagnostic, not approval.
    worker_code = _v1_semantic_process_executor.__code__
    serialized_worker_loaded = (
        "production_generation_lock" in worker_code.co_names
        and "semantic" in worker_code.co_consts
        and "V1 semantic worker queue timed out" in worker_code.co_consts
    )
    blocked_writer = False
    with production_generation_read() as pinned:
        try:
            with production_generation_lock(exclusive=True):
                blocked_writer = False
        except ProductionGenerationBusy:
            blocked_writer = True
        generation = pinned.generation
    return {
        "state": "PUBLIC_READER_PROBE_PASS"
                 if all(loaded.values()) and blocked_writer
                 else "PUBLIC_READER_PROBE_BLOCKED",
        "mcp_pid": os.getpid(),
        "loaded_reader_functions": loaded,
        "writer_blocked_during_read": blocked_writer,
        "generation": generation,
        "semantic_worker_serialization_loaded": serialized_worker_loaded,
        "child_semantic_execution_attested": False,
        "safe_to_activate": False,
    }


def inspect_rag_integrity() -> dict[str, Any]:
    """Audit the selected RAG generation with the reader lock held.

    This cannot activate, publish or delete a generation.
    """
    _ensure_project_root()
    from rag.runtime.versioned_live_integrity import inspect_pinned_index
    from rag.runtime.production_generation_read import production_generation_read
    with production_generation_read() as pinned:
        return inspect_pinned_index(pinned)


def get_rag_status() -> dict[str, Any]:
    _ensure_project_root()

    from rag.runtime.status import build_rag_status
    # Preserve EMPTY semantics and avoid creating a production lock in an
    # environment where no index exists (legacy MCP status unit tests).
    if _v1_legacy_index_missing():
        return build_rag_status().to_dict()
    from rag.runtime.production_generation_read import production_generation_read
    with production_generation_read() as pinned:
        return build_rag_status(_generation_paths=pinned).to_dict()


def index_rag(
    *,
    project_id: str,
    project_root: str,
    scope: str = "BOTH",
    paths: Optional[list[str]] = None,
    execute: bool = False,
) -> dict[str, Any]:
    _ensure_project_root()
    if project_id == "codebridge":
        import json
        import os
        config_path = (
            Path(os.environ.get("LOCALAPPDATA") or str(Path.home()))
            / "CodeBridge-MCP-Bridge" / "rag_v1_semantic.json"
        )
        if config_path.is_file():
            config = json.loads(config_path.read_text(encoding="utf-8-sig"))
            if config.get("enabled") is True and config.get("project_id") == project_id:
                approved = config.get("repository_root")
                if not approved or Path(project_root).resolve() != Path(approved).resolve():
                    raise PermissionError("CodeBridge index plan requires the approved repository root")
                if execute:
                    from rag.runtime.index_request import RagIndexExecutionUnavailableError
                    raise RagIndexExecutionUnavailableError(
                        "RAG V1 incremental publication is blocked until source approval, "
                        "production generation locking and operator maintenance authorization"
                    )

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
    payload = result.to_dict()
    if not execute and project_id == "codebridge":
        import json
        import os
        from rag.runtime.incremental_preflight import assess_incremental_plan

        config_path = (
            Path(os.environ.get("LOCALAPPDATA") or str(Path.home()))
            / "CodeBridge-MCP-Bridge"
            / "rag_v1_semantic.json"
        )
        if config_path.is_file():
            config = json.loads(config_path.read_text(encoding="utf-8-sig"))
            root = Path(project_root).resolve()
            approved = Path(config.get("repository_root") or root.parent).resolve()
            if (
                config.get("enabled") is True
                and config.get("project_id") == project_id
                and root == approved
            ):
                payload["plan"]["incremental_preview"] = assess_incremental_plan(
                    payload["plan"],
                    full_inventory=scope == "BOTH" and not paths,
                )
                # A deterministic review receipt is informational only:
                # it never grants a right to publish. Large inventories must
                # be curated into small, explicitly selected source batches.
                candidate_rows = payload["plan"]["candidates"]
                if 0 < len(candidate_rows) <= 20:
                    from rag.runtime.incremental_preview_confirmation import snapshot_preview
                    from rag.runtime.incremental_review_contract import build_review_contract
                    from rag.runtime.incremental_preview_view import describe_incremental_preview

                    payload["plan"]["preview_view"] = describe_incremental_preview(
                        payload["plan"], payload["plan"]["incremental_preview"]
                    )
                    snapshot = snapshot_preview(project_id, root, candidate_rows)
                    payload["plan"]["review_contract"] = build_review_contract(
                        snapshot, project_id, root
                    )
                    payload["plan"]["review_status"] = "FINGERPRINTED_NOT_APPROVED"
                else:
                    payload["plan"]["review_status"] = "SOURCE_SELECTION_REQUIRED"
    return payload


def _v1_legacy_index_missing() -> bool:
    """A missing legacy index has no reader to pin; preserve error mapping."""
    from rag.runtime.status import resolve_rag_sqlite_path

    index = resolve_rag_sqlite_path()
    return not index.is_file() and not (index.parent / "active-generation.json").is_file()


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

    if project_id == "codebridge" and _v1_legacy_index_missing():
        # Preserve the existing structured INDEX_UNAVAILABLE error without
        # creating a lock inside a missing index directory.
        result = search_context(
            query=query, project_id=project_id,
            source_types=tuple(source_types or ()), top_k=top_k,
            path_filter=path_filter, branch=branch,
            semantic_executor=None,
        )
    elif project_id == "codebridge":
        from rag.runtime.production_generation_read import production_generation_read

        # Hold the reader lock across the complete search, including the
        # semantic subprocess, so SQLite and vectors share one generation.
        with production_generation_read() as pinned:
            result = search_context(
                query=query, project_id=project_id,
                source_types=tuple(source_types or ()), top_k=top_k,
                path_filter=path_filter, branch=branch,
                sqlite_path=pinned.sqlite,
                semantic_executor=_RAG_SEARCH_EXECUTOR,
            )
    else:
        result = search_context(
            query=query, project_id=project_id,
            source_types=tuple(source_types or ()), top_k=top_k,
            path_filter=path_filter, branch=branch,
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

    if project_id == "codebridge" and _v1_legacy_index_missing():
        result = get_context(
            project_id=project_id, chunk_ids=tuple(chunk_ids),
            include_document_content=include_document_content,
            project_root=project_root, allow_stale=allow_stale,
        )
    elif project_id == "codebridge":
        from rag.runtime.production_generation_read import production_generation_read

        with production_generation_read() as pinned:
            result = get_context(
                project_id=project_id,
                chunk_ids=tuple(chunk_ids),
                include_document_content=include_document_content,
                project_root=project_root,
                allow_stale=allow_stale,
                sqlite_path=pinned.sqlite,
            )
    else:
        result = get_context(
            project_id=project_id,
            chunk_ids=tuple(chunk_ids),
            include_document_content=include_document_content,
            project_root=project_root,
            allow_stale=allow_stale,
        )
    return result.to_dict()
