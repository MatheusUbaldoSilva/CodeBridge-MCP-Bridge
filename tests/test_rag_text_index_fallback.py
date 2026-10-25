"""The text indexing path must use bounded memory and CPU fallback

Mock-only tests no real model GPU or production index touched
"""
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from rag.runtime.production_index import _write_vectors


class TextStagingFallbackTests(unittest.TestCase):
    def test_text_stage_uses_fallback_manager_and_unloads(self):
        from rag.models import artifact_install, embedding, fallback
        from rag.index import qdrant_local, vector_ids
        from qdrant_client import models
        from rag.models.backend_policy import (
            TEXT_SEARCH_CONTEXT_TOKENS, TEXT_SEARCH_UBATCH_TOKENS,
        )

        events = []
        manager = Mock()
        manager.active_lifecycle = Mock()
        manager.load.side_effect = lambda **kwargs: events.append("load")
        manager.unload.side_effect = lambda **kwargs: events.append("unload")
        index = Mock()
        vector = SimpleNamespace(values=[0.1] * 1024)
        text_embedding = Mock()
        text_embedding.embed_document.return_value = vector
        row = ("chunk", "doc", "small content", "DOCUMENTATION", "docs/a.md", 1, 1, "a"*64, "dev", "b"*40)

        def make_manager(config):
            self.assertEqual(config.context_size, TEXT_SEARCH_CONTEXT_TOKENS)
            self.assertEqual(config.ubatch_size, TEXT_SEARCH_UBATCH_TOKENS)
            self.assertEqual(config.parallel_slots, 1)
            return manager

        patches = [
            patch.object(qdrant_local,"open_qdrant_local",return_value=index),
            patch.object(qdrant_local,"close_qdrant_local",side_effect=lambda *_:events.append("close")),
            patch.object(qdrant_local,"ensure_vector_collections"),
            patch.object(artifact_install,"resolve_selected_model_path",return_value=Path("C:/fake-embedding.gguf")),
            patch.object(fallback.TextModelFallbackManager,"auto",side_effect=make_manager),
            patch.object(embedding,"TextEmbeddingClient",return_value=text_embedding),
            patch.object(vector_ids,"deterministic_vector_point_id",return_value="12345678-0000-0000-0000-000000000000"),
            patch.object(models,"PointStruct",side_effect=lambda **kwargs:kwargs),
        ]
        with patches[0],patches[1],patches[2],patches[3],patches[4],patches[5],patches[6],patches[7]:
            _write_vectors(Path("C:/isolated-vector"),"codebrige-mcp-rag",[row],[])
        self.assertEqual(events,["load","unload","close"])
        self.assertEqual(index.upsert.call_count,1)
        self.assertTrue(index.upsert.call_args.kwargs["wait"])
        text_embedding.embed_document.assert_called_once_with("small content")

    def test_text_embedding_failure_still_unloads(self):
        from rag.models import artifact_install, embedding, fallback
        from rag.index import qdrant_local
        index = Mock()
        manager = Mock()
        manager.active_lifecycle = Mock()
        embedding_client = Mock()
        embedding_client.embed_document.side_effect = RuntimeError("synthetic failure")
        row = ("chunk", "doc", "small content", "DOCUMENTATION", "docs/a.md", 1, 1, "a"*64, "dev", "b"*40)
        with (
            patch.object(qdrant_local,"open_qdrant_local",return_value=index),
            patch.object(qdrant_local,"close_qdrant_local") as closing,
            patch.object(qdrant_local,"ensure_vector_collections"),
            patch.object(artifact_install,"resolve_selected_model_path",return_value=Path("C:/fake.gguf")),
            patch.object(fallback.TextModelFallbackManager,"auto",return_value=manager),
            patch.object(embedding,"TextEmbeddingClient",return_value=embedding_client),
        ):
            with self.assertRaisesRegex(RuntimeError,"synthetic failure"):
                _write_vectors(Path("C:/isolated-vector"),"codebrige-mcp-rag",[row],[])
        manager.unload.assert_called_once()
        closing.assert_called_once_with(index)
        index.upsert.assert_not_called()

if __name__ == "__main__":
    unittest.main()
