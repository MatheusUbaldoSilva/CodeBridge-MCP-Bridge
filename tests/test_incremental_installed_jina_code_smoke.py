"""Opt-in proof that pinned Jina Code performs actual local embeddings."""
from pathlib import Path
import unittest

from rag.models.code_artifact_install import resolve_selected_code_model_path
from rag.models.code_lifecycle import CodeModelLifecycle, build_code_server_config
from rag.models.code_embedding import CodeEmbeddingClient, CodeRetrievalTask
from rag.models.lifecycle import ModelLifecycleState

class InstalledJinaCodeSmoke(unittest.TestCase):
    def test_code_embeddings_load_and_release(self):
        exe=Path(r"C:\llama\llama-server.exe")
        model=resolve_selected_code_model_path()
        if not exe.is_file() or not model.is_file():
            self.skipTest("pinned Jina Code or llama-server unavailable")
        life=CodeModelLifecycle(build_code_server_config(
            executable_path=exe,model_path=model,port=0,
            gpu_layers=99,device="CUDA0"))
        life.load(timeout_seconds=90)
        try:
            vector=CodeEmbeddingClient(life).embed_passage(
                CodeRetrievalTask.NL2CODE,"def total(a, b): return a + b")
            self.assertGreater(len(vector.values),0)
            self.assertEqual(life.snapshot().state,ModelLifecycleState.READY)
        finally:
            life.unload(timeout_seconds=15)
        self.assertNotEqual(life.snapshot().state,ModelLifecycleState.READY)
