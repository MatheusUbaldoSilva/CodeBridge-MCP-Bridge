"""Real SQLite/FTS5 + Qdrant search on isolated index, with controlled query embedding."""
import sys
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qdrant_client import models
from test_incremental_bundle_validate import fixture
from rag.contracts import SearchQuery
from rag.models.embedding import TEXT_EMBEDDING_DIMENSION
from rag.index.fts5 import initialize_fts5
from rag.index.qdrant_local import open_qdrant_local, close_qdrant_local
from rag.runtime.query_classifier import QueryRoute
from rag.runtime.production_search import search_persistent_semantic
from rag.runtime.generation_activation import activate_test_generation
from rag.runtime.generation_protected_session import protected_generation_retirement
from rag.runtime.generation_process_lock import GenerationBusy


class RealGenerationSearchTests(unittest.TestCase):
    def test_real_sqlite_and_qdrant_keep_same_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "codebridge-rag-generation-test"
            for name in ("one", "two"):
                folder = root / "generations" / name
                folder.mkdir(parents=True)
                fixture(folder)
                database = sqlite3.connect(folder / "rag_index.sqlite3")
                try:
                    initialize_fts5(database)
                    database.commit()
                finally:
                    database.close()
                shutil.rmtree(folder / "qdrant")
                client = open_qdrant_local(folder / "qdrant")
                try:
                    client.create_collection("code", vectors_config=models.VectorParams(
                        size=3, distance=models.Distance.COSINE))
                    client.create_collection("text", vectors_config=models.VectorParams(
                        size=TEXT_EMBEDDING_DIMENSION, distance=models.Distance.COSINE))
                    client.upsert("text", points=[models.PointStruct(
                        id=42, vector=[1.0]+[0.0]*(TEXT_EMBEDDING_DIMENSION-1),
                        payload={"project_namespace": "a", "chunk_id": "c1",
                                 "document_id": "d1", "content": "hello",
                                 "source_type": "DOCUMENTATION", "path": "a.md"})])
                finally:
                    close_qdrant_local(client)
            activate_test_generation(root, "one")
            def switch_during_embedding(query, executable):
                activate_test_generation(root, "two")
                with self.assertRaises(GenerationBusy):
                    with protected_generation_retirement(root, "one"):
                        pass
                return [1.0]+[0.0]*(TEXT_EMBEDDING_DIMENSION-1)
            with patch("rag.runtime.production_search._embed_text", side_effect=switch_during_embedding):
                results = search_persistent_semantic(
                    SearchQuery(query="hello", project_id="a", top_k=5),
                    QueryRoute.TEXT, experimental_generation_root=root)
            self.assertTrue(results)
            self.assertTrue(any("VECTOR_TEXT_COSINE" in item.retrieval_modes
                                for item in results))
            self.assertEqual(results[0].content, "hello")

if __name__ == "__main__":
    unittest.main()
