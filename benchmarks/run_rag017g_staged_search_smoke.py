"""Real Jina staged index + semantic search smoke, without production publication."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
import shutil

from rag.contracts import SearchQuery
from rag.runtime.index_request import plan_rag_index,RagIndexScope
from rag.runtime.production_index import build_staged_index
from rag.runtime.production_search import search_persistent_semantic
from rag.runtime.query_classifier import QueryRoute

with TemporaryDirectory() as td:
    root=Path(td)
    (root/"notes.md").write_text("# Retrieval\nSemantic embeddings make document context searchable through the vector index.",encoding="utf-8")
    plan=plan_rag_index("rag017g-smoke",root,scope=RagIndexScope.TEXT,paths=("notes.md",))
    output=build_staged_index(plan)
    stage=Path(output["staging_path"])
    try:
        with patch("rag.runtime.production_search.build_rag_status",return_value=SimpleNamespace(index={"state":"READY"})):
            with patch("rag.runtime.production_search.resolve_rag_sqlite_path",return_value=stage/"rag_index.sqlite3"):
                with patch("rag.runtime.production_search.resolve_qdrant_local_path",return_value=stage/"qdrant"):
                    query=SearchQuery(query="searchable document context through semantic embeddings",project_id="rag017g-smoke",top_k=5)
                    hits=search_persistent_semantic(query,QueryRoute.TEXT)
        assert hits and hits[0].metadata.project_id=="rag017g-smoke",hits
        assert hits[0].metadata.path=="notes.md"
        print("RAG017G_END_TO_END_SMOKE_OK",len(hits),output["state"])
    finally:
        shutil.rmtree(stage)
