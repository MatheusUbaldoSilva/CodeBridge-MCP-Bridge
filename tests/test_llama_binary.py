"""Todas as IAs usam a mesma copia do llama-server."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for path in (str(ROOT / "app_rewrite"), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from rag import llama_binary  # noqa: E402
import local_ai_server as srv  # noqa: E402


class SharedBinaryTest(unittest.TestCase):
    def test_default_and_env_override(self):
        with patch.dict(os.environ, {llama_binary.ENV_VAR: ""}):
            self.assertEqual(llama_binary.llama_server_path(), Path(r"C:\llama\llama-server.exe"))
        with patch.dict(os.environ, {llama_binary.ENV_VAR: r"D:\outra\llama-server.exe"}):
            self.assertEqual(llama_binary.llama_server_path(), Path(r"D:\outra\llama-server.exe"))

    def test_local_ai_uses_shared_copy_when_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            shared = Path(tmp) / "llama-server.exe"
            shared.write_text("x")
            with patch.dict(os.environ, {llama_binary.ENV_VAR: str(shared)}):
                self.assertEqual(srv.resolve_server_exe(), shared)
            with patch.dict(os.environ, {llama_binary.ENV_VAR: str(Path(tmp) / "nao_existe.exe")}):
                self.assertEqual(srv.resolve_server_exe(), srv.OWN_SERVER_EXE)

    def test_rag_search_default_is_shared_copy(self):
        import inspect
        from rag.runtime import production_search
        defaults = [p.default for p in inspect.signature(production_search.search_production_index).parameters.values()
                    if p.name == "llama_server"] if hasattr(production_search, "search_production_index") else []
        source = inspect.getsource(production_search)
        self.assertNotIn(r'Path(r"C:\llama\llama-server.exe")', source)
        self.assertIn("llama_server_path()", source)
        for value in defaults:
            self.assertEqual(Path(value), llama_binary.llama_server_path())

    def test_rag_index_uses_shared_copy(self):
        import inspect
        from rag.runtime import production_index
        source = inspect.getsource(production_index)
        self.assertNotIn(r'Path(r"C:\llama\llama-server.exe")', source)
        self.assertIn("llama_server_path()", source)


if __name__ == "__main__":
    unittest.main()
