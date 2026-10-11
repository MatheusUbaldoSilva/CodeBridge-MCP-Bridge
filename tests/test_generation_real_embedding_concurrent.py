"""Live embedding + concurrent generation switch, isolated Windows regression."""
from __future__ import annotations
import shutil
import sqlite3
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from qdrant_client import models
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_validate import fixture
from rag.contracts import SearchQuery
from rag.index.fts5 import initialize_fts5
from rag.index.qdrant_local import open_qdrant_local, close_qdrant_local
from rag.models.artifact_install import resolve_selected_model_path
from rag.models.embedding import TEXT_EMBEDDING_DIMENSION
from rag.runtime.production_search import _embed_text, search_persistent_semantic
from rag.runtime.query_classifier import QueryRoute
from rag.runtime.generation_activation import activate_test_generation
from rag.runtime.generation_protected_session import protected_generation_retirement
from rag.runtime.generation_process_lock import GenerationBusy


class LiveConcurrentGenerationTest(unittest.TestCase):
    def test_live_search_survives_switch_and_releases_storage(self):
        server = Path(r"C:\llama\llama-server.exe")
        if not server.is_file() or not resolve_selected_model_path().is_file():
            self.skipTest("llama or pinned model unavailable")
        vector = _embed_text("hello", server)
        self.assertEqual(len(vector), TEXT_EMBEDDING_DIMENSION)
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
                    client.upsert("text", points=[models.PointStruct(id=42, vector=list(vector),
                        payload={"project_namespace": "a", "chunk_id": "c1", "document_id": "d1",
                                 "content": "hello", "source_type": "DOCUMENTATION", "path": "a.md"})], wait=True)
                finally:
                    close_qdrant_local(client)
            activate_test_generation(root, "one")
            entered = threading.Event()
            release = threading.Event()
            outcome = {}

            def search_worker():
                try:
                    from unittest.mock import patch
                    real_embedding = _embed_text
                    def delayed_embedding(query, executable):
                        entered.set()
                        if not release.wait(30):
                            raise TimeoutError("switch not signaled")
                        return real_embedding(query, executable)
                    with patch("rag.runtime.production_search._embed_text", side_effect=delayed_embedding):
                        outcome["results"] = search_persistent_semantic(
                            SearchQuery(query="hello", project_id="a", top_k=5),
                            QueryRoute.TEXT, llama_server=server,
                            experimental_generation_root=root)
                except Exception as exc:
                    outcome["error"] = repr(exc)

            worker = threading.Thread(target=search_worker, daemon=True)
            worker.start()
            try:
                self.assertTrue(entered.wait(10), "search did not acquire generation")
                activate_test_generation(root, "two")
                with self.assertRaises(GenerationBusy):
                    with protected_generation_retirement(root, "one"):
                        pass
            finally:
                release.set()
                worker.join(timeout=40)
            self.assertFalse(worker.is_alive(), "live embedding search timed out")
            self.assertNotIn("error", outcome, outcome.get("error"))
            results = outcome["results"]
            self.assertTrue(any("VECTOR_TEXT_COSINE" in result.retrieval_modes for result in results))
            self.assertEqual(results[0].content, "hello")
            with protected_generation_retirement(root, "one") as retired:
                self.assertTrue(retired.is_dir())


if __name__ == "__main__":
    unittest.main()
