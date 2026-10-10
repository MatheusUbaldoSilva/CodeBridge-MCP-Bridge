"""Central RAG headless Qt and read-only status smoke."""
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
from rag_panel import RagPanel, _rag_operation

class RagPanelSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_widget_construction(self):
        with patch.object(RagPanel, "_run"):
            panel = RagPanel()
            self.assertTrue(panel.search_btn.isEnabled())
            self.assertEqual(panel.project.text(), "codebridge")
            panel.close()

    def test_plan_shows_candidates_without_indexing(self):
        with patch.object(RagPanel, "_run"):
            panel = RagPanel()
        panel._complete("plan", {"plan": {
            "candidate_count": 2, "text_candidate_count": 1,
            "code_candidate_count": 1, "denied_count": 1,
            "unsupported_count": 3, "sensitive_count": 0,
            "candidates": [
                {"path": "notes/readme.md", "text_eligible": True, "code_eligible": False},
                {"path": "src/app.py", "text_eligible": False, "code_eligible": True},
            ],
        }}, "")
        self.assertEqual(panel.candidates.rowCount(), 2)
        self.assertIn("Elegiveis: 2", panel.plan_summary.text())
        self.assertIn("Nenhuma indexacao", panel.notice.text())
        panel.close()

    def test_status_read_only(self):
        status = _rag_operation("status", {})
        self.assertIn("index", status)
        self.assertIn("projects", status)

if __name__ == "__main__":
    unittest.main()
