import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rag.sources.code_inventory import is_code_source
from rag.sources.document_inventory import is_document_source
from rag.sources.exclusion_policy import (
    DenyReason,
    classify_denied_path,
    is_denied_path,
)


class RagExclusionPolicyTests(unittest.TestCase):
    def test_handoff_directory_exclusions(self):
        cases = {
            ".git/objects/aa/bb": DenyReason.GIT_OBJECTS,
            ".venv/Lib/site-packages/pkg.py": DenyReason.VIRTUAL_ENV,
            "venv/bin/tool.py": DenyReason.VIRTUAL_ENV,
            "node_modules/pkg/index.js": DenyReason.NODE_MODULES,
            "build/generated.py": DenyReason.BUILD_OUTPUT,
            "dist/app.js": DenyReason.BUILD_OUTPUT,
            "__pycache__/module.pyc": DenyReason.CACHE,
            ".pytest_cache/v/cache/nodeids": DenyReason.CACHE,
            ".mypy_cache/3.12/meta.json": DenyReason.CACHE,
            ".ruff_cache/content": DenyReason.CACHE,
            ".cache/model.bin": DenyReason.CACHE,
            "backups/source.py": DenyReason.BACKUP,
            "backup/config.json": DenyReason.BACKUP,
            "tmp/output.json": DenyReason.TEMPORARY,
            "temp/output.py": DenyReason.TEMPORARY,
        }
        for path, reason in cases.items():
            with self.subTest(path=path):
                self.assertEqual(classify_denied_path(path), reason)

    def test_binary_extensions_are_denied(self):
        for path in (
            "installer/CodeBridge.exe",
            "native/helper.dll",
            "lib/module.so",
            "artifacts/data.bin",
            "assets/icon.png",
            "assets/sound.mp3",
            "archive/source.zip",
            "python/module.pyc",
        ):
            with self.subTest(path=path):
                self.assertEqual(
                    classify_denied_path(path),
                    DenyReason.BINARY,
                )

    def test_env_credentials_private_keys_and_tokens_are_denied(self):
        cases = {
            ".env": DenyReason.ENV_FILE,
            ".env.local": DenyReason.ENV_FILE,
            "config/credentials.json": DenyReason.CREDENTIAL,
            "config/client_secret.json": DenyReason.CREDENTIAL,
            "keys/id_rsa": DenyReason.PRIVATE_KEY,
            "keys/id_ed25519": DenyReason.PRIVATE_KEY,
            "certs/private.pem": DenyReason.PRIVATE_KEY,
            "certs/client.key": DenyReason.PRIVATE_KEY,
            "config/api_token.json": DenyReason.TOKEN,
            "config/access-token.txt": DenyReason.TOKEN,
            "config/api_key.yaml": DenyReason.TOKEN,
        }
        for path, reason in cases.items():
            with self.subTest(path=path):
                self.assertEqual(classify_denied_path(path), reason)

    def test_backups_and_temporaries_are_denied(self):
        cases = {
            "src/main.py.bak": DenyReason.BACKUP,
            "src/main.py.backup": DenyReason.BACKUP,
            "src/main.py~": DenyReason.BACKUP,
            "src/.main.py.swp": DenyReason.TEMPORARY,
            "src/output.tmp": DenyReason.TEMPORARY,
            "src/output.temp": DenyReason.TEMPORARY,
        }
        for path, reason in cases.items():
            with self.subTest(path=path):
                self.assertEqual(classify_denied_path(path), reason)

    def test_denylist_wins_over_code_allowlist(self):
        paths = (
            ".venv/tool.py",
            "node_modules/app.js",
            "dist/config.json",
            "backup/script.ps1",
            "config/api_token.json",
        )
        for path in paths:
            with self.subTest(path=path):
                self.assertTrue(is_code_source(path))
                self.assertTrue(is_denied_path(path))

    def test_denylist_wins_over_document_allowlist(self):
        paths = (
            "backups/README.md",
            "tmp/ROADMAP.md",
            "node_modules/README.md",
        )
        for path in paths:
            with self.subTest(path=path):
                self.assertTrue(is_document_source(path))
                self.assertTrue(is_denied_path(path))

    def test_legitimate_project_sources_are_not_denied(self):
        for path in (
            "app_rewrite/runtime.py",
            "author_mcp/mcp_server.py",
            "docs/ROADMAP.md",
            "README.md",
            "browser_extension/codebridge_chatgpt_timer/manifest.json",
            "installer/CodeBridge.nsi",
            "installer/version.nsh",
            "requirements.txt",
        ):
            with self.subTest(path=path):
                self.assertFalse(is_denied_path(path))

    def test_current_dist_artifacts_are_denied_even_by_nonbinary_suffix(self):
        self.assertEqual(
            classify_denied_path("installer/dist/CodeBridge-Setup.exe"),
            DenyReason.BUILD_OUTPUT,
        )
        self.assertEqual(
            classify_denied_path("installer/dist/CodeBridge-Setup.sha256"),
            DenyReason.BUILD_OUTPUT,
        )

    def test_path_traversal_is_denied(self):
        self.assertEqual(
            classify_denied_path("../outside/project.py"),
            DenyReason.PATH_TRAVERSAL,
        )
        self.assertEqual(
            classify_denied_path("docs/../../secret.txt"),
            DenyReason.PATH_TRAVERSAL,
        )

    def test_windows_paths_are_normalized(self):
        self.assertEqual(
            classify_denied_path(r".venv\Scripts\tool.py"),
            DenyReason.VIRTUAL_ENV,
        )

    def test_empty_path_is_rejected(self):
        with self.assertRaises(ValueError):
            classify_denied_path("")


if __name__ == "__main__":
    unittest.main()
