"""Controlled semantic subprocess for a registered immutable project RAG.

Only accepts a previously authorized, fingerprinted local candidate. It cannot
change the public CodeBridge RAG pointer, build indexes, or publish data.
"""
from __future__ import annotations

import json
import sys

from rag.contracts import SearchQuery, SourceType
from rag.runtime.isolated_project_index import resolve_isolated_project
from rag.runtime.production_generation_read import SearchStoragePaths
from rag.runtime.production_search import search_persistent_semantic
from rag.runtime.query_classifier import QueryRoute
from rag.runtime.search_service import search_result_to_dict



def _pinned_request_scratch_only() -> None:
    """Opt-in DQ-E-D-3C-A parser on REAL worker entrypoint, TEMP ONLY.

    Shares validated request contract with the synthetic worker but MUST NOT
    invoke semantic search, registered-project lookup, or a model in this mode.
    The real pinned semantic inference path remains intentionally unavailable.
    """
    from pathlib import Path
    from rag.runtime.knowledge_deletion_semantic_request_lab import (
        PinnedSemanticRequestV1, verify_pinned_semantic_request_lab,
    )
    raw = sys.stdin.readline(8193)
    if len(raw) > 8192:
        raise ValueError("scratch pinned request exceeds 8192 bytes")
    request = PinnedSemanticRequestV1.parse(json.loads(raw))
    result = verify_pinned_semantic_request_lab(
        request, catalog_file=Path(sys.argv[2]) / "project-indexes.json",
        laboratory_mode=True,
    )
    json.dump(result, sys.stdout, ensure_ascii=True)
    sys.stdout.write("\n")


def _pinned_snapshot_scratch_only() -> None:
    """Read only authorized TEMP SQLite namespace; no model or Qdrant."""
    from pathlib import Path
    from rag.runtime.knowledge_deletion_semantic_request_lab import (
        PinnedSemanticRequestV1,
    )
    from rag.runtime.knowledge_deletion_semantic_snapshot_lab import (
        read_pinned_semantic_snapshot_lab,
    )
    raw=sys.stdin.readline(8193)
    if len(raw)>8192:
        raise ValueError("scratch snapshot request exceeds 8192 bytes")
    request=PinnedSemanticRequestV1.parse(json.loads(raw))
    result=read_pinned_semantic_snapshot_lab(
        request,catalog_file=Path(sys.argv[2])/"project-indexes.json",
        laboratory_mode=True,
    )
    json.dump(result,sys.stdout,ensure_ascii=True)
    sys.stdout.write("\n")


def main() -> None:
    if len(sys.argv) == 2 and sys.argv[1] == "--pinned-mac-scratch":
        # Opt-in scratch-only protocol. No model, Qdrant or project resolver.
        from rag.runtime.knowledge_deletion_mac_child_lab import main as mac_lab_main
        if mac_lab_main()!=0:
            raise PermissionError("scratch MAC channel rejected")
        return
    if len(sys.argv) != 1:
        if len(sys.argv) == 3 and sys.argv[1] == "--pinned-scratch-only":
            return _pinned_request_scratch_only()
        if len(sys.argv) == 3 and sys.argv[1] == "--pinned-scratch-snapshot":
            return _pinned_snapshot_scratch_only()
        if len(sys.argv) == 5 and sys.argv[1] == "--pinned-scratch-supervised":
            # Opt-in DEV scratch-only child. NEVER falls back to legacy
            # project resolution, Qdrant, or production semantic inference.
            from rag.runtime.knowledge_deletion_liveness_child_lab import (
                run_supervised_scratch_child_lab,
            )
            return run_supervised_scratch_child_lab(
                sys.argv[2],sys.argv[3],sys.argv[4],
            )
        raise PermissionError("unsupported isolated project worker arguments")
    data = json.load(sys.stdin)
    if not isinstance(data, dict) or not isinstance(data.get("project_id"),str):
        raise PermissionError("project namespace is required")
    index = resolve_isolated_project(data["project_id"])
    if index is None:
        raise PermissionError("isolated project is not enabled")
    route = QueryRoute(data["route"])
    if route is QueryRoute.LEXICAL_ONLY:
        raise ValueError("lexical-only queries must not start an embedding model")
    top_k = data["top_k"]
    if type(top_k) is not int or not 1 <= top_k <= 20:
        raise ValueError("invalid top_k")
    query = SearchQuery(
        query=data["query"],project_id=index.project_id,top_k=top_k,
        source_types=tuple(SourceType(value) for value in data["source_types"]),
        path_filter=data.get("path_filter"),branch=data.get("branch"),
    )
    pinned = SearchStoragePaths(
        generation=index.generation,
        sqlite=index.sqlite,qdrant=index.qdrant,manifest=index.manifest,
    )
    results = search_persistent_semantic(query,route,_generation_paths=pinned)
    json.dump([search_result_to_dict(item) for item in results],sys.stdout,ensure_ascii=True)
    sys.stdout.write("\n")


if __name__=="__main__":
    main()
