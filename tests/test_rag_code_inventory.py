import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rag.sources.code_inventory import (
    ALLOWED_CODE_EXTENSIONS,
    CodeSourceKind,
    classify_code_path,
    is_code_source,
)


class RagCodeInventoryTests(unittest.TestCase):
    def test_handoff_extensions_are_allowed(self):
        expected = {
            ".c", ".cc", ".cpp", ".h", ".hpp",
            ".py", ".ps1", ".bat", ".cmd", ".sh",
            ".js", ".ts", ".json", ".yaml", ".yml", ".toml",
        }
        self.assertTrue(expected.issubset(ALLOWED_CODE_EXTENSIONS))

    def test_current_codebridge_extra_extensions_are_allowed(self):
        for extension in (".html", ".css", ".nsi", ".nsh"):
            with self.subTest(extension=extension):
                self.assertIn(extension, ALLOWED_CODE_EXTENSIONS)

    def test_code_languages_are_classified(self):
        for path in (
            "src/main.cpp",
            "include/main.hpp",
            "app/module.py",
            "script.ps1",
            "deploy.cmd",
            "tool.sh",
        ):
            with self.subTest(path=path):
                self.assertEqual(
                    classify_code_path(path),
                    CodeSourceKind.CODE,
                )

    def test_web_sources_are_classified(self):
        for path in (
            "web/app.js",
            "web/app.ts",
            "web/index.html",
            "web/site.css",
        ):
            with self.subTest(path=path):
                self.assertEqual(
                    classify_code_path(path),
                    CodeSourceKind.WEB,
                )

    def test_structured_configuration_is_classified(self):
        for path in (
            "config.json",
            "config.yaml",
            "config.yml",
            "pyproject.toml",
        ):
            with self.subTest(path=path):
                self.assertEqual(
                    classify_code_path(path),
                    CodeSourceKind.CONFIG,
                )

    def test_installer_sources_are_classified(self):
        self.assertEqual(
            classify_code_path("installer/CodeBridge.nsi"),
            CodeSourceKind.INSTALLER,
        )
        self.assertEqual(
            classify_code_path("installer/version.nsh"),
            CodeSourceKind.INSTALLER,
        )

    def test_requirements_is_exact_manifest_not_generic_txt(self):
        self.assertEqual(
            classify_code_path("requirements.txt"),
            CodeSourceKind.DEPENDENCY_MANIFEST,
        )
        self.assertEqual(
            classify_code_path("author_mcp/requirements.txt"),
            CodeSourceKind.DEPENDENCY_MANIFEST,
        )
        self.assertIsNone(classify_code_path("logs/output.txt"))

    def test_documentation_and_binary_assets_are_not_code_sources(self):
        for path in (
            "README.md",
            "docs/ROADMAP.md",
            "installer/dist/CodeBridge-Setup.exe",
            "assets/codebridge.png",
            "assets/completion.mp3",
            "installer/dist/CodeBridge-Setup.sha256",
        ):
            with self.subTest(path=path):
                self.assertFalse(is_code_source(path))

    def test_env_and_private_key_are_not_code_sources(self):
        self.assertIsNone(classify_code_path(".env"))
        self.assertIsNone(classify_code_path("id_rsa"))
        self.assertIsNone(classify_code_path("private.pem"))

    def test_windows_paths_are_normalized(self):
        self.assertEqual(
            classify_code_path(r"app_rewrite\main.py"),
            CodeSourceKind.CODE,
        )

    def test_empty_path_is_rejected(self):
        with self.assertRaises(ValueError):
            classify_code_path("")


if __name__ == "__main__":
    unittest.main()
