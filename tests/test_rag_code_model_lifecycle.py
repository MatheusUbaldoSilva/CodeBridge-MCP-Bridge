import tempfile
import unittest
from pathlib import Path

from rag.models.code_backend_policy import (
    CODE_RECOMMENDED_CONTEXT_TOKENS,
    CODE_RECOMMENDED_UBATCH_SIZE,
)
from rag.models.code_lifecycle import (
    CodeModelLifecycle,
    build_code_server_config,
)
from rag.models.lifecycle import (
    ModelLifecycleState,
    build_llama_server_argv,
)


class RagCodeLifecycleTests(unittest.TestCase):
    def test_code_config_freezes_context_and_ubatch(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = build_code_server_config(
                executable_path=root / "server.exe",
                model_path=root / "code.gguf",
                port=19130,
                device="CUDA0",
            )

        self.assertEqual(
            config.context_size,
            CODE_RECOMMENDED_CONTEXT_TOKENS,
        )
        self.assertEqual(
            config.ubatch_size,
            CODE_RECOMMENDED_UBATCH_SIZE,
        )
        self.assertEqual(config.pooling, "last")
        self.assertEqual(config.host, "127.0.0.1")

    def test_argv_contains_code_context_flags(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = build_code_server_config(
                executable_path=root / "server.exe",
                model_path=root / "code.gguf",
                port=19130,
                device="CUDA0",
            )
            argv = build_llama_server_argv(
                config,
                resolved_port=19130,
            )

        self.assertEqual(
            argv[argv.index("--ctx-size") + 1],
            "8192",
        )
        self.assertEqual(
            argv[argv.index("--ubatch-size") + 1],
            "8192",
        )
        self.assertEqual(
            argv[argv.index("--device") + 1],
            "CUDA0",
        )

    def test_generic_text_config_keeps_context_flags_optional(self):
        from rag.models.lifecycle import LlamaServerConfig

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = LlamaServerConfig(
                executable_path=root / "server.exe",
                model_path=root / "text.gguf",
            )
            argv = build_llama_server_argv(
                config,
                resolved_port=19131,
            )

        self.assertNotIn("--ctx-size", argv)
        self.assertNotIn("--ubatch-size", argv)

    def test_constructor_is_side_effect_free(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = build_code_server_config(
                executable_path=root / "server.exe",
                model_path=root / "code.gguf",
            )
            manager = CodeModelLifecycle(config)
            self.assertEqual(
                manager.state,
                ModelLifecycleState.UNLOADED,
            )
            self.assertFalse(
                (root / "server.log").exists()
            )


if __name__ == "__main__":
    unittest.main()
