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


def main() -> None:
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
