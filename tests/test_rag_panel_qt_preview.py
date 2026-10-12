"""Headless Qt checks for the source-tree RAG preview; never invokes indexing."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app_rewrite"))
from PySide6.QtWidgets import QApplication, QMessageBox
from rag_panel import RagPanel
from rag.runtime.incremental_preview_confirmation import snapshot_preview


class RagPanelQtPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "a.md").write_text("initial", encoding="utf-8")
        with patch.object(RagPanel, "refresh"):
            self.panel = RagPanel()
        self.addCleanup(self.panel.close)
        self.panel.folder.setText(str(self.root))
        self.panel.project_id = "demo"

    def _response(self):
        return {"plan": {"project_id": "demo", "candidates": [{"path": "a.md"}],
                         "denied_count": 0, "unsupported_count": 0},
                "incremental": {"project_id": "demo", "new_files": ["a.md"], "new_count": 1,
                    "modified_files": [], "modified_count": 0,
                    "unchanged_files": [], "unchanged_count": 0,
                    "unknown_files": [], "unknown_count": 0},
                "preview_start": snapshot_preview("demo", self.root, [{"path": "a.md"}])}

    def _pending(self):
        self.panel._plan_request = (self.panel._preview_revision, "demo", str(self.root.resolve()))
        self.panel._busy = True

    def test_preview_display_and_cancel_after_completion(self):
        self._pending()
        self.panel.notice.setText("Carregando...")
        self.panel._complete("plan", self._response(), "")
        self.assertEqual(self.panel.notice.text(), "")
        self.assertTrue(self.panel.confirm_preview_btn.isEnabled())
        self.assertEqual(self.panel.candidates.count(), 1)
        self.assertFalse(self.panel.index_btn.isEnabled())
        self.panel.cancel_preview()
        self.assertEqual(self.panel.candidates.count(), 0)
        self.assertFalse(self.panel.confirm_preview_btn.isEnabled())

    def test_authorization_rehearsal_does_not_publish(self):
        self._pending()
        self.panel._complete("plan", self._response(), "")
        self.assertTrue(self.panel.review_auth_btn.isEnabled())
        def accept(dialog):
            self.assertIn("Projeto: demo\n", dialog.text())
            self.assertIn("Arquivos conferidos: 1\n", dialog.text())
            self.assertIn("Identificador da revisao: ", dialog.text())
            self.assertNotIn(r"\\n", dialog.text())
            self.assertGreaterEqual(dialog.minimumWidth(), 500)
            self.assertEqual([b.text() for b in dialog.buttons()],
                             ["Confirmar simulacao", "Cancelar"])
            dialog.buttons()[0].click()
        with patch.object(QMessageBox, "exec", accept):
            self.panel.review_authorization()
        self.assertFalse(self.panel.index_btn.isEnabled())
        self.assertIn("Nenhum indice alterado", self.panel.notice.text())
        self.panel.cancel_preview()
        self.assertFalse(self.panel.review_auth_btn.isEnabled())

    def test_changed_during_authorization_dialog_is_blocked(self):
        self._pending()
        self.panel._complete("plan", self._response(), "")
        def change_after_review(dialog):
            (self.root / "a.md").write_text("changed after opening", encoding="utf-8")
            dialog.buttons()[0].click()
        with patch.object(QMessageBox, "exec", change_after_review), patch.object(
                QMessageBox, "warning") as warning:
            self.panel.review_authorization()
        warning.assert_called_once()
        self.assertIsNone(self.panel._preview_snapshot)
        self.assertFalse(self.panel.review_auth_btn.isEnabled())
        self.assertFalse(self.panel.index_btn.isEnabled())

    def test_authorization_rehearsal_rejects_stale_file(self):
        self._pending()
        self.panel._complete("plan", self._response(), "")
        (self.root / "a.md").write_text("changed", encoding="utf-8")
        with patch.object(QMessageBox, "warning") as warning, patch.object(QMessageBox, "question") as question:
            self.panel.review_authorization()
        warning.assert_called_once()
        question.assert_not_called()
        self.assertFalse(self.panel.index_btn.isEnabled())

    def test_cancel_while_busy_discards_late_completion(self):
        self._pending()
        reply = self._response()
        self.panel.cancel_preview()
        self.panel._complete("plan", reply, "")
        self.assertEqual(self.panel.candidates.count(), 0)
        self.assertIsNone(self.panel._preview_snapshot)
        self.assertFalse(self.panel.index_btn.isEnabled())

    def test_project_change_discards_late_completion(self):
        self._pending()
        reply = self._response()
        self.panel.cancel_preview()
        self.panel.project_id = "other"
        self.panel._complete("plan", reply, "")
        self.assertEqual(self.panel.candidates.count(), 0)
        self.assertFalse(self.panel.confirm_preview_btn.isEnabled())

    def test_modified_file_rejected_by_qt_confirmation(self):
        self._pending()
        self.panel._complete("plan", self._response(), "")
        (self.root / "a.md").write_text("updated", encoding="utf-8")
        with patch.object(QMessageBox, "warning") as warning:
            self.panel.confirm_preview()
        warning.assert_called_once()
        self.assertIsNone(self.panel._preview_snapshot)
        self.assertFalse(self.panel.confirm_preview_btn.isEnabled())
        self.assertFalse(self.panel.index_btn.isEnabled())


if __name__ == "__main__":
    unittest.main()
