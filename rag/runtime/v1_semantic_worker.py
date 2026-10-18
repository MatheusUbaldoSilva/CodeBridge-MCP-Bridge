"""Isolated semantic search worker for the installed CodeBridge RAG V1.

Runs with an explicitly approved Python environment containing qdrant-client.
Never mutates, rebuilds, promotes, or deletes the persistent index.
"""
from __future__ import annotations

import json
import sys

from rag.contracts import SearchQuery, SourceType
from rag.runtime.query_classifier import QueryRoute
from rag.runtime.production_search import search_persistent_semantic
from rag.runtime.search_service import search_result_to_dict


def main() -> None:
    data = json.load(sys.stdin)
    if data.get("project_id") != "codebridge":
        raise PermissionError("V1 semantic worker only permits project codebridge")
    route = QueryRoute(data["route"])
    if route is QueryRoute.LEXICAL_ONLY:
        raise ValueError("Lexical search must remain in the MCP service")
    query = SearchQuery(
        query=data["query"],
        project_id=data["project_id"],
        top_k=int(data["top_k"]),
        source_types=tuple(SourceType(value) for value in data["source_types"]),
        path_filter=data.get("path_filter"),
        branch=data.get("branch"),
    )
    results = search_persistent_semantic(query, route)
    json.dump([search_result_to_dict(item) for item in results], sys.stdout, ensure_ascii=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
