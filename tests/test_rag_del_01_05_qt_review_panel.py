import os
import sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
os.environ["QT_QPA_PLATFORM"]="offscreen"
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"app_rewrite"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from rag_deletion_review_panel import KnowledgeRemovalReviewPanel

class ReviewPanelTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.panel=KnowledgeRemovalReviewPanel()
        self.panel.set_project_files("demo",["a.cpp","b.cpp"])
        self.addCleanup(self.panel.close)
    @patch("rag_deletion_review_panel.build_deletion_review")
    def test_shows_preview_only(self, service):
        service.return_value={"display_text":"SIMULAÇÃO: nenhum removido","review_sha256":"x","execution_enabled":False}
        self.panel.selector.items.item(0).setCheckState(Qt.CheckState.Checked)
        self.panel.selector.preview_button.click()
        self.assertIn("SIMULAÇÃO",self.panel.details.toPlainText())
        service.assert_called_once_with("demo",["a.cpp"])
    @patch("rag_deletion_review_panel.build_deletion_review")
    def test_public_project_blocked(self, service):
        self.panel.set_project_files("codebridge",["a.cpp"])
        self.assertFalse(self.panel.selector.preview_button.isEnabled())
        self.panel.review_selected(["a.cpp"])
        service.assert_not_called()
    @patch("rag_deletion_review_panel.build_deletion_review")
    def test_backend_rejection_visible(self, service):
        service.side_effect=ValueError("inactive generation")
        self.panel.review_selected(["a.cpp"])
        self.assertIn("Prévia bloqueada",self.panel.details.toPlainText())
        self.assertIsNone(self.panel.last_review)
    def test_changing_project_clears_prior_review(self):
        self.panel.last_review={"some":"old"}
        self.panel.set_project_files("other",["c.cpp"])
        self.assertIsNone(self.panel.last_review)
        self.assertFalse(self.panel.selector.preview_button.isEnabled())
