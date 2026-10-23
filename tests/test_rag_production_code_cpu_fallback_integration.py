"""Isolated wiring tests; never starts llama, touches GPU, or public RAG."""
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from rag.runtime.production_index import _write_vectors


class CodeFallbackWiringTests(unittest.TestCase):
    def test_code_wiring_has_no_runtime_side_effect_on_import(self):
        from rag.runtime import production_index
        self.assertTrue(callable(production_index._write_vectors))

    def test_code_embeddings_use_manager_and_cleanup(self):
        from rag.models import fallback
        from rag.models import code_embedding
        from rag.index import qdrant_local
        from rag.models import code_artifact_install
        from rag.index import vector_ids
        from qdrant_client import models
        events=[]
        life=Mock()
        manager=Mock()
        manager.active_lifecycle=life
        manager.load.side_effect=lambda **kw: events.append("load")
        manager.unload.side_effect=lambda **kw: events.append("unload")
        embedded=Mock()
        embedded.embed_passage.return_value=SimpleNamespace(values=[0.25,0.75])
        fake_client=Mock()
        row=("chunk","document","sample code","CODE","sample.py",1,2,
             "a"*64,"branch","b"*40)
        def make_manager(**kw):
            self.assertEqual(kw["gpu_config"].device,"CUDA0")
            self.assertEqual(kw["cpu_config"].device,"none")
            self.assertEqual(kw["cpu_config"].gpu_layers,0)
            self.assertIs(kw["lifecycle_factory"].__name__ == "CodeModelLifecycle", True)
            return manager
        patches=[
            patch.object(qdrant_local,"open_qdrant_local",return_value=fake_client),
            patch.object(qdrant_local,"close_qdrant_local",side_effect=lambda *a:events.append("close")),
            patch.object(qdrant_local,"ensure_vector_collections"),
            patch.object(code_artifact_install,"resolve_selected_code_model_path",return_value=Path("C:/synthetic.gguf")),
            patch.object(fallback,"TextModelFallbackManager",side_effect=make_manager),
            patch.object(code_embedding,"CodeEmbeddingClient",return_value=embedded),
            patch.object(vector_ids,"deterministic_vector_point_id",return_value="id"),
            patch.object(models,"PointStruct",side_effect=lambda **kw:kw),
        ]
        with patches[0],patches[1],patches[2],patches[3],patches[4],patches[5],patches[6],patches[7]:
            _write_vectors(Path("C:/synthetic-qdrant"),"codebridge",[],[row])
        self.assertEqual(events,["load","unload","close"])
        embedded.embed_passage.assert_called_once()
        self.assertEqual(fake_client.upsert.call_count,1)
        self.assertTrue(fake_client.upsert.call_args.kwargs["wait"])

    def test_failed_embedding_closes_manager_without_upsert(self):
        from rag.models import fallback
        from rag.models import code_embedding
        from rag.index import qdrant_local
        from rag.models import code_artifact_install
        from rag.index import vector_ids
        from qdrant_client import models
        events=[]
        life=Mock()
        manager=Mock()
        manager.active_lifecycle=life
        manager.load.side_effect=lambda **kw: events.append("load")
        manager.unload.side_effect=lambda **kw: events.append("unload")
        embedded=Mock()
        embedded.embed_passage.side_effect=RuntimeError("synthetic embedding failure")
        fake_client=Mock()
        row=("chunk","document","sample code","CODE","sample.py",1,2,
             "a"*64,"branch","b"*40)
        def make_manager(**kw):
            self.assertEqual(kw["gpu_config"].device,"CUDA0")
            self.assertEqual(kw["cpu_config"].device,"none")
            self.assertEqual(kw["cpu_config"].gpu_layers,0)
            self.assertIs(kw["lifecycle_factory"].__name__ == "CodeModelLifecycle", True)
            return manager
        patches=[
            patch.object(qdrant_local,"open_qdrant_local",return_value=fake_client),
            patch.object(qdrant_local,"close_qdrant_local",side_effect=lambda *a:events.append("close")),
            patch.object(qdrant_local,"ensure_vector_collections"),
            patch.object(code_artifact_install,"resolve_selected_code_model_path",return_value=Path("C:/synthetic.gguf")),
            patch.object(fallback,"TextModelFallbackManager",side_effect=make_manager),
            patch.object(code_embedding,"CodeEmbeddingClient",return_value=embedded),
            patch.object(vector_ids,"deterministic_vector_point_id",return_value="id"),
            patch.object(models,"PointStruct",side_effect=lambda **kw:kw),
        ]
        with patches[0],patches[1],patches[2],patches[3],patches[4],patches[5],patches[6],patches[7]:
            with self.assertRaisesRegex(RuntimeError,"synthetic embedding failure"):
                _write_vectors(Path("C:/synthetic-qdrant"),"codebridge",[],[row])
        self.assertEqual(events,["load","unload","close"])
        embedded.embed_passage.assert_called_once()
        fake_client.upsert.assert_not_called()


if __name__=="__main__":
    unittest.main()
