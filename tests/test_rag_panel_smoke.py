"""Smoke tests for simplified RAG center."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app_rewrite"))
sys.path.insert(0, str(ROOT))
from PySide6.QtWidgets import QApplication
from rag_panel import RagPanel, _rag_operation, _source, _content
from rag_projects import validate_preview_folder, create_project, list_projects

class RagPanelSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make_panel(self):
        with patch.object(RagPanel, "_run"):
            return RagPanel()

    def test_three_pages_and_protected_indexing(self):
        panel = self.make_panel()
        self.assertEqual(panel.pages.count(), 3)
        self.assertEqual([x.text() for x in panel.nav_buttons],
                         ["Meus arquivos", "Pesquisar", "Adicionar"])
        self.assertFalse(panel.index_btn.isEnabled())
        self.assertTrue(panel.folder.isReadOnly())
        panel.set_page(2)
        self.assertEqual(panel.pages.currentIndex(), 2)
        panel.close()

    def test_documents_and_search(self):
        panel = self.make_panel()
        panel._complete("documents", [{"path":"docs/guide.md", "type":"DOCUMENTATION","count":1}], "")
        self.assertEqual(panel.files.count(), 1)
        panel.files.setCurrentRow(0)
        self.assertIn("docs/guide.md", panel.file_details.toPlainText())
        panel._complete("search", {"results":[{"content":"hello world","metadata":{"path":"docs/guide.md"}}]}, "")
        self.assertEqual(panel.results.count(), 1)
        self.assertIn("docs/guide.md", panel.results.item(0).text())
        self.assertIn("hello world", panel.preview.toPlainText())
        panel.close()

    def test_plan_is_preview_only(self):
        panel = self.make_panel()
        panel._complete("plan", {"plan":{
            "candidate_count":1, "denied_count":2, "sensitive_count":0,
            "unsupported_count":3, "candidates":[{"path":"notes/test.md"}],
        }}, "")
        self.assertEqual(panel.candidates.count(), 1)
        self.assertIn("1 arquivos", panel.plan_summary.text())
        self.assertFalse(panel.index_btn.isEnabled())
        panel.close()

    def test_source_helpers(self):
        self.assertEqual(_source({"metadata":{"path":"notes/a.md"}}),"notes/a.md")
        self.assertEqual(_content({"content":"sample"}),"sample")

    def test_project_registry_and_preview_safety(self):
        import tempfile
        with tempfile.TemporaryDirectory() as root:
            with patch('rag_projects.registry_path', return_value=Path(root) / 'projects.json'):
                self.assertEqual(create_project('new-world-pvp'), 'new-world-pvp')
                self.assertIn('new-world-pvp', list_projects())
                with self.assertRaises(ValueError):
                    create_project('wrong name')
            blocked = Path(root) / 'CodeBridge_Recovery_TEST'
            blocked.mkdir()
            with self.assertRaises(ValueError):
                validate_preview_folder(blocked)
            documents = Path(root) / 'docs'
            documents.mkdir()
            (documents / 'test.md').write_text('sample', encoding='utf-8')
            self.assertEqual(validate_preview_folder(documents), 1)

    def test_online_indicator(self):
        panel = self.make_panel()
        with patch.object(panel, "_run"):
            panel._complete("status", {"index": {"state": "READY"}, "projects": []}, "")
        self.assertEqual(panel.rag_status.text(), "RAG: ONLINE")
        panel._complete("status", {}, "unavailable")
        self.assertEqual(panel.rag_status.text(), "RAG: OFFLINE")
        panel.close()

    def test_status_read_only(self):
        status = _rag_operation("status", {})
        self.assertIn("index", status)
        self.assertIn("projects", status)

if __name__ == "__main__":
    unittest.main()
