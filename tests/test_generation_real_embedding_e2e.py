"""Opt-in GPU embedding through real SQLite FTS5 + local Qdrant.

Requires installed pinned Jina model and llama-server. Runs only when invoked
explicitly; never reads or modifies production RAG storage.
"""
from __future__ import annotations
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from qdrant_client import models
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from test_incremental_bundle_validate import fixture
from rag.contracts import SearchQuery
from rag.index.fts5 import initialize_fts5
from rag.index.qdrant_local import open_qdrant_local, close_qdrant_local
from rag.runtime.production_search import _embed_text, search_persistent_semantic
from rag.runtime.query_classifier import QueryRoute
from rag.runtime.generation_activation import activate_test_generation
from rag.models.embedding import TEXT_EMBEDDING_DIMENSION
from rag.models.artifact_install import resolve_selected_model_path


class RealEmbeddingEndToEndTests(unittest.TestCase):
    def test_gpu_model_vector_retrieval(self):
        executable = Path(r"C:\llama\llama-server.exe")
        if not executable.is_file() or not resolve_selected_model_path().is_file():
            self.skipTest("local model or llama-server absent")
        vector = _embed_text("hello", executable)
        self.assertEqual(len(vector), TEXT_EMBEDDING_DIMENSION)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "codebridge-rag-generation-test"
            generation = root / "generations" / "one"
            generation.mkdir(parents=True)
            fixture(generation)
            connection = sqlite3.connect(generation / "rag_index.sqlite3")
            try:
                initialize_fts5(connection)
                connection.commit()
            finally:
                connection.close()
            # Replace only this temporary fixture\u0027s 3-D Qdrant store
            # with a clean index matching the actual model dimension.
            import shutil
            shutil.rmtree(generation / "qdrant")
            q = open_qdrant_local(generation / "qdrant")
            try:
                q.create_collection("code", vectors_config=models.VectorParams(
                    size=3, distance=models.Distance.COSINE))
                q.create_collection("text", vectors_config=models.VectorParams(
                    size=TEXT_EMBEDDING_DIMENSION, distance=models.Distance.COSINE))
                q.upsert("text", points=[models.PointStruct(
                    id=42, vector=list(vector), payload={
                        "project_namespace": "a", "chunk_id": "c1",
                        "document_id": "d1", "content": "hello",
                        "source_type": "DOCUMENTATION", "path": "a.md",
                    })], wait=True)
            finally:
                close_qdrant_local(q)
            activate_test_generation(root, "one")
            results = search_persistent_semantic(
                SearchQuery(query="hello", project_id="a", top_k=5),
                QueryRoute.TEXT, llama_server=executable,
                experimental_generation_root=root,
            )
            self.assertTrue(any("VECTOR_TEXT_COSINE" in result.retrieval_modes
                                for result in results))
            self.assertEqual(results[0].content, "hello")


if __name__ == "__main__":
    unittest.main()
