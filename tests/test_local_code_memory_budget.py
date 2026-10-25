"""CB-LOCAL.05: bounded Jina Code query runtime and safe parallelism contract."""
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rag.models.code_backend_policy import (
    CODE_SEARCH_CONTEXT_TOKENS,
    CODE_SEARCH_UBATCH_TOKENS,
    CODE_SEARCH_PARALLEL_SLOTS,
)
from rag.models.code_lifecycle import build_code_server_config
from rag.models.lifecycle import LlamaServerConfig, build_llama_server_argv
from rag.models.code_embedding import CodeRetrievalTask
from rag.runtime import production_search
from rag.runtime import resident_models


class CodeSearchMemoryBudgetTests(unittest.TestCase):
    def test_policy_and_server_args(self):
        self.assertEqual(
            (CODE_SEARCH_CONTEXT_TOKENS, CODE_SEARCH_UBATCH_TOKENS, CODE_SEARCH_PARALLEL_SLOTS),
            (2048, 128, 1),
        )
        cfg = build_code_server_config(
            executable_path=Path("llama-server.exe"),
            model_path=Path("model.gguf"),
            context_size=2048, ubatch_size=128, parallel_slots=1,
        )
        args = build_llama_server_argv(cfg, resolved_port=49210)
        self.assertEqual(args[args.index("--ctx-size") + 1], "2048")
        self.assertEqual(args[args.index("--ubatch-size") + 1], "128")
        self.assertEqual(args[args.index("--parallel") + 1], "1")

    def test_parallel_slots_invalid_fail_closed(self):
        for value in (0, -1, True, "1"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    LlamaServerConfig(
                        executable_path=Path("server.exe"),
                        model_path=Path("model.gguf"),
                        parallel_slots=value,
                    )

    def test_regular_ondemand_code_search_uses_bounded_context(self):
        manager = MagicMock()
        manager.active_lifecycle = object()
        with patch("rag.models.fallback.TextModelFallbackManager.auto", return_value=manager) as make, \
             patch.object(production_search, "resolve_selected_code_model_path", return_value=Path("code.gguf")), \
             patch.object(production_search, "CodeEmbeddingClient") as embedding:
            embedding.return_value.embed_query.return_value = SimpleNamespace(values=(0.4,))
            result = production_search._embed_code("find code", Path("llama-server.exe"))
        self.assertEqual(result, (0.4,))
        cfg = make.call_args.args[0]
        self.assertEqual((cfg.context_size, cfg.ubatch_size, cfg.parallel_slots), (2048, 128, 1))
        embedding.return_value.embed_query.assert_called_once_with(CodeRetrievalTask.NL2CODE, "find code")
        manager.load.assert_called_once()
        manager.unload.assert_called_once()

    def test_resident_code_search_uses_bounded_context(self):
        model = MagicMock()
        pool = resident_models.ResidentEmbeddingPool()
        with patch.object(resident_models, "CodeModelLifecycle", return_value=model) as make, \
             patch.object(resident_models, "resolve_selected_code_model_path", return_value=Path("code.gguf")), \
             patch.object(resident_models, "CodeEmbeddingClient") as embedding:
            embedding.return_value.embed_query.return_value = SimpleNamespace(values=(0.5,))
            result = pool.embed_code("find code", Path("llama-server.exe"))
        self.assertEqual(result, (0.5,))
        cfg = make.call_args.args[0]
        self.assertEqual((cfg.context_size, cfg.ubatch_size, cfg.parallel_slots), (2048, 128, 1))
        pool.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
