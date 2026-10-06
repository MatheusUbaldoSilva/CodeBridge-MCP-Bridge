import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rag.sources.document_inventory import (
    DocumentCategory,
    classify_document_path,
    is_document_source,
)


class RagDocumentInventoryTests(unittest.TestCase):
    def test_readme_anywhere_is_documentation(self):
        self.assertEqual(
            classify_document_path("README.md"),
            DocumentCategory.README,
        )
        self.assertEqual(
            classify_document_path("manual_tests/README.md"),
            DocumentCategory.README,
        )

    def test_docs_markdown_is_documentation(self):
        self.assertEqual(
            classify_document_path("docs/ARCHITECTURE.md"),
            DocumentCategory.DOCUMENTATION,
        )

    def test_handoff_and_roadmap_have_specific_categories(self):
        self.assertEqual(
            classify_document_path(
                "docs/HANDOFF_RAG_JINA_CODEBRIDGE_2_0_2026-10-06.md"
            ),
            DocumentCategory.HANDOFF,
        )
        self.assertEqual(
            classify_document_path("docs/ROADMAP.md"),
            DocumentCategory.ROADMAP,
        )

    def test_patch_note_patterns_are_recognized(self):
        for path in (
            "docs/PATCH_NOTES_2026-10-06.md",
            "patch-note-001.txt",
            "PATCHNOTE.md",
        ):
            with self.subTest(path=path):
                self.assertEqual(
                    classify_document_path(path),
                    DocumentCategory.PATCH_NOTE,
                )

    def test_audit_patterns_are_recognized(self):
        for path in (
            "docs/AUDIT_RAG_002.md",
            "auditoria/relatorio_auditoria.txt",
        ):
            with self.subTest(path=path):
                self.assertEqual(
                    classify_document_path(path),
                    DocumentCategory.AUDIT,
                )

    def test_requirements_manifests_are_not_documentation(self):
        self.assertIsNone(classify_document_path("requirements.txt"))
        self.assertIsNone(
            classify_document_path("author_mcp/requirements.txt")
        )

    def test_generic_txt_outside_docs_is_not_implicitly_documentation(self):
        self.assertFalse(is_document_source("random/output.txt"))

    def test_markdown_outside_docs_remains_documentation(self):
        self.assertEqual(
            classify_document_path("author_mcp/PROTOCOL.md"),
            DocumentCategory.DOCUMENTATION,
        )

    def test_windows_style_paths_are_normalized(self):
        self.assertEqual(
            classify_document_path(r"docs\ROADMAP.md"),
            DocumentCategory.ROADMAP,
        )

    def test_empty_path_is_rejected(self):
        with self.assertRaises(ValueError):
            classify_document_path("")


if __name__ == "__main__":
    unittest.main()
