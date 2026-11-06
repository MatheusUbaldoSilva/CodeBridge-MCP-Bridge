"""CLOSE-04 source GUI integration tests: locked delete inside actual RagPanel."""
import os
import sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app_rewrite"))

from PySide6.QtWidgets import QApplication
from rag_panel import RagPanel


class IntegratedLockedDeleteTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        with patch.object(RagPanel, "refresh"):
            self.gui = RagPanel()
        self.addCleanup(self.gui.close)
        self.delete = self.gui.deletion_review_panel.delete_button

    def test_visible_in_real_files_page_but_disabled(self):
        self.assertEqual(self.delete.text(), "Excluir conhecimentos")
        self.assertIs(self.gui.deletion_review_panel.selector.parent(),
                      self.gui.deletion_review_panel)
        self.assertFalse(self.delete.isEnabled())
        self.assertIn("origem", self.delete.toolTip())

    def test_project_change_cannot_unlock_delete(self):
        self.gui.deletion_review_panel.set_project_files("private", ["alpha.py"])
        self.assertFalse(self.delete.isEnabled())
        self.gui.deletion_review_panel.set_project_files("codebridge", ["beta.py"])
        self.assertFalse(self.delete.isEnabled())

    def test_forged_enabled_review_does_not_unlock_delete(self):
        panel = self.gui.deletion_review_panel
        panel.set_project_files("private", ["alpha.py"])
        with patch("rag_deletion_review_panel.build_deletion_review", return_value={
            "display_text": "Review preview", "execution_enabled": True,
            "activation_authorized": True
        }):
            panel.review_selected(["alpha.py"])
        self.assertFalse(self.delete.isEnabled())
        self.assertIn("Prévia bloqueada", panel.details.toPlainText())
