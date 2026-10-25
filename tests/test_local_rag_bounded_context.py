"""Constrain local Jina text query inference memory without changing model/index pins."""
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rag.models.backend_policy import TEXT_SEARCH_CONTEXT_TOKENS, TEXT_SEARCH_UBATCH_TOKENS
from rag.models.lifecycle import build_llama_server_argv
from rag.runtime import production_search
from rag.runtime import resident_models


class TextInferenceMemoryPolicyTests(unittest.TestCase):
    def test_bounded_server_arguments(self):
        self.assertEqual(TEXT_SEARCH_CONTEXT_TOKENS, 8192)
        self.assertEqual(TEXT_SEARCH_UBATCH_TOKENS, 512)

    def test_ondemand_text_uses_bounded_context(self):
        manager = MagicMock()
        manager.active_lifecycle = object()
        with patch("rag.models.fallback.TextModelFallbackManager.auto", return_value=manager) as make, \
             patch.object(production_search, "resolve_selected_model_path", return_value=Path("test.gguf")), \
             patch.object(production_search, "TextEmbeddingClient") as embedding:
            embedding.return_value.embed_query.return_value = SimpleNamespace(values=(0.3,))
            self.assertEqual(production_search._embed_text("hello", Path("llama-server.exe")), (0.3,))
        cfg = make.call_args.args[0]
        self.assertEqual(cfg.context_size, TEXT_SEARCH_CONTEXT_TOKENS)
        self.assertEqual(cfg.ubatch_size, TEXT_SEARCH_UBATCH_TOKENS)
        command = build_llama_server_argv(cfg, resolved_port=11110)
        self.assertEqual(command[command.index("--ctx-size") + 1], "8192")
        self.assertEqual(command[command.index("--ubatch-size") + 1], "512")
        manager.load.assert_called_once()
        manager.unload.assert_called_once()

    def test_resident_text_uses_same_context(self):
        model = MagicMock()
        pool = resident_models.ResidentEmbeddingPool()
        with patch.object(resident_models, "TextModelLifecycle", return_value=model) as make, \
             patch.object(resident_models, "resolve_selected_model_path", return_value=Path("test.gguf")), \
             patch.object(resident_models, "TextEmbeddingClient") as embedding:
            embedding.return_value.embed_query.return_value = SimpleNamespace(values=(0.5,))
            self.assertEqual(pool.embed_text("hello", Path("llama-server.exe")), (0.5,))
        cfg = make.call_args.args[0]
        self.assertEqual(cfg.context_size, TEXT_SEARCH_CONTEXT_TOKENS)
        self.assertEqual(cfg.ubatch_size, TEXT_SEARCH_UBATCH_TOKENS)
        pool.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
