"""Read-only MCP route for independently registered project indexes.

The CodeBridge public project keeps using its existing generation reader.
Registered extra projects use an isolated SQLite/Qdrant candidate, with
semantic inference in the installed dependency-capable Python subprocess.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import time
from typing import Any

from rag.runtime.isolated_project_index import resolve_isolated_project


def _verify_pinned_source(source_root: Path, source_path: str | None, expected_sha: str | None) -> dict[str, Any]:
    """Match the original indexer bytes-to-text SHA, including Windows CRLF."""
    from rag.chunking.provenance import source_sha256

    if source_path is None or expected_sha is None:
        return {"status":"UNVERIFIED","reason":"SOURCE_METADATA_MISSING","current_sha256":None}
    root=source_root.resolve()
    path=(root/source_path).resolve()
    if not path.is_relative_to(root):
        return {"status":"UNVERIFIED","reason":"SOURCE_OUTSIDE_PINNED_ROOT","current_sha256":None}
    if not path.is_file():
        return {"status":"STALE","reason":"SOURCE_MISSING","current_sha256":None}
    try:
        # Path.read_text() silently normalizes CRLF to LF on Windows. The index
        # stored the original decoded bytes, so verify those same bytes.
        actual=source_sha256(path.read_bytes().decode("utf-8",errors="replace"))
    except (OSError,UnicodeError):
        return {"status":"UNVERIFIED","reason":"SOURCE_READ_FAILED","current_sha256":None}
    return {
        "status":"FRESH" if actual==expected_sha else "STALE",
        "reason":"SHA_MATCH" if actual==expected_sha else "SHA_MISMATCH",
        "current_sha256":actual,
    }


def semantic_isolated_project(query: Any, route: Any) -> tuple[Any, ...]:
    from rag.contracts import SearchResult, SourceMetadata, SourceType
    from rag.runtime.production_generation_lock import (
        ProductionGenerationBusy, production_generation_lock,
    )

    index = resolve_isolated_project(query.project_id)
    if index is None:
        raise PermissionError("project index is not enabled")
    if not 1 <= query.top_k <= 20:
        raise ValueError("project search top_k must be between 1 and 20")
    payload = {
        "query":query.query,"project_id":query.project_id,
        "source_types":[item.value for item in query.source_types],
        "top_k":query.top_k,"path_filter":query.path_filter,
        "branch":query.branch,"route":route.value,
    }
    deadline = time.monotonic()+100
    while True:
        try:
            with production_generation_lock(exclusive=True, channel="semantic"):
                try:
                    completed = subprocess.run(
                        [str(index.python_executable),"-m","rag.runtime.isolated_project_worker"],
                        cwd=str(Path(__file__).resolve().parents[2]),
                        input=json.dumps(payload), text=True,
                        capture_output=True, timeout=180, check=False,
                    )
                except subprocess.TimeoutExpired as exc:
                    raise RuntimeError("isolated project inference timed out") from exc
            break
        except ProductionGenerationBusy as exc:
            if time.monotonic() >= deadline:
                raise RuntimeError("semantic process queue timed out") from exc
            time.sleep(0.2)
    if completed.returncode != 0:
        raise RuntimeError("isolated project inference failed: "+completed.stderr[-650:])
    items = json.loads(completed.stdout)
    return tuple(
        SearchResult(
            chunk_id=item["chunk_id"],
            document_id=item["document_id"],
            content=item["content"],
            metadata=SourceMetadata(**{
                **item["metadata"],
                "source_type":SourceType(item["metadata"]["source_type"]),
            }),
            score=float(item["score"]),
            rank=int(item["rank"]),
            retrieval_modes=tuple(item.get("retrieval_modes",())),
            stale=bool(item.get("stale",False)),
        )
        for item in items
    )


def search_isolated_project(
    *,
    query: str,
    project_id: str,
    source_types: tuple[str, ...] = (),
    top_k: int = 10,
    path_filter: str | None = None,
    branch: str | None = None,
):
    from rag.runtime.search_service import search_context

    project = resolve_isolated_project(project_id)
    if project is None:
        raise PermissionError("project is not registered for isolated search")
    result = search_context(
        query=query,project_id=project_id,
        source_types=source_types,top_k=top_k,
        path_filter=path_filter,branch=branch,
        sqlite_path=project.sqlite,
        semantic_executor=semantic_isolated_project,
    )
    payload = result.to_dict()
    for item in payload.get("results",[]):
        raw=item["metadata"]
        verification=_verify_pinned_source(
            project.source_root,raw.get("path"),raw.get("sha256"),
        )
        item["source_verification"]=verification
        item["stale"]=bool(item.get("stale")) or verification["status"]!="FRESH"
    # Prefer verified results, never silently discard an older source.
    payload["results"].sort(
        key=lambda row: (row["source_verification"]["status"]!="FRESH",row["rank"])
    )
    for ordinal,item in enumerate(payload["results"],1):
        item["rank"]=ordinal
    return payload


def get_isolated_project_context(
    *,
    project_id: str,
    chunk_ids: list[str],
    include_document_content: bool = False,
    project_root: str | None = None,
    allow_stale: bool = False,
) -> dict[str, Any]:
    from rag.runtime.context_service import get_context
    project = resolve_isolated_project(project_id)
    if project is None:
        raise PermissionError("project is not registered for isolated context")
    if project_root is not None and Path(project_root).resolve() != project.source_root:
        raise PermissionError("context root cannot override pinned project source")
    if allow_stale:
        raise PermissionError("isolated project context must be fresh")
    result=get_context(
        project_id=project_id,
        chunk_ids=tuple(chunk_ids),
        include_document_content=include_document_content,
        # Validate provenance below using the same raw-byte SHA as indexing.
        # The shared legacy verifier normalizes CRLF and is not valid here.
        project_root=None,
        allow_stale=False,
        sqlite_path=project.sqlite,
    ).to_dict()
    from rag.runtime.errors import RagStaleResultError
    for item in result["items"]:
        verification=_verify_pinned_source(
            project.source_root,item.get("path"),item.get("sha256"),
        )
        if verification["status"]!="FRESH":
            raise RagStaleResultError(
                f"pinned project source changed: {item['chunk_id']} ({verification['reason']})"
            )
    return result
