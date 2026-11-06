import os
import sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app_rewrite"))

from PySide6.QtWidgets import QApplication
from rag_deletion_review_panel import KnowledgeRemovalReviewPanel


class LockedDeleteActionTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.panel = KnowledgeRemovalReviewPanel()
        self.addCleanup(self.panel.close)

    def test_forged_review_never_enables_delete(self):
        self.panel.set_project_files("private", ["one.py"])
        self.assertFalse(self.panel.delete_button.isEnabled())
        self.assertFalse(self.panel.delete_button.isHidden())
        self.assertIn("Confira", self.panel.delete_status.text())
        with patch("rag_deletion_review_panel.build_deletion_review", return_value={
            "display_text": "Prévia", "execution_enabled": True
        }):
            self.panel.review_selected(["one.py"])
        self.assertIsNone(self.panel.last_review)
        self.assertFalse(self.panel.delete_button.isEnabled())
        self.panel.delete_button.click()
        self.assertIn("Prévia bloqueada", self.panel.details.toPlainText())

    def test_genuine_review_enables_delete(self):
        self.panel.set_project_files("private", ["one.py", "two.py"])
        genuine = {"state": "READ_ONLY_REVIEW", "project_id": "private",
                   "selected_paths": ["one.py"], "review_sha256": "a" * 64,
                   "execution_enabled": False, "documents_to_remove": 1,
                   "display_text": "Prévia real"}
        with patch("rag_deletion_review_panel.build_deletion_review", return_value=genuine):
            self.panel.review_selected(["one.py"])
        self.assertTrue(self.panel.delete_button.isEnabled())
        self.assertFalse(self.panel.undo_button.isEnabled())

    def test_fail_closed_on_project_change_and_failure(self):
        self.panel.set_project_files("private", ["one.py"])
        self.panel.last_review = {"untrusted": True}
        self.panel.set_project_files("codebridge", ["one.py"])
        self.assertFalse(self.panel.delete_button.isEnabled())
        self.assertIsNone(self.panel.last_review)
        self.assertIn("índice público", self.panel.delete_status.text())
        self.panel.set_project_files("private", ["one.py"])
        with patch("rag_deletion_review_panel.build_deletion_review", side_effect=RuntimeError("stale")):
            self.panel.review_selected(["one.py"])
        self.assertFalse(self.panel.delete_button.isEnabled())
        self.assertIn("Prévia bloqueada", self.panel.details.toPlainText())
