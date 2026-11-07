"""Aviso de exclusao: contexto, Manter exclusao e Desfazer -> Manual."""
import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app_rewrite"))
sys.path.insert(0, str(ROOT))
from PySide6.QtWidgets import QApplication
import rag_deletion_review_panel as module

TX = "a" * 32


class BannerTextTests(unittest.TestCase):
    def test_auto_sync_removal_without_note(self):
        text = module.pending_banner_text(
            {"transaction": TX, "kind": "REMOVE", "at": "2026-11-07T17:29:11+00:00"},
            {"transaction": TX, "removed": 1, "at": "2026-11-07T17:29:12+00:00"})
        self.assertTrue(text.startswith("1 arquivo removido do conhecimento pela atualiza"))
        self.assertIn("fechar o CodeBridge", text)

    def test_files_and_origin_from_note(self):
        files = ["docs/a.md", "b.py", "c/d.txt", "e.md"]
        text = module.pending_banner_text(
            {"transaction": TX, "removed_files": files, "origin": "TELA"})
        self.assertTrue(text.startswith("4 arquivos removidos do conhecimento por voc"))
        self.assertIn("a.md, b.py, d.txt e mais 1", text)

    def test_unknown_context(self):
        text = module.pending_banner_text({"transaction": TX})
        self.assertTrue(text.startswith("Exclus"))


class PanelKeepTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make_panel(self, pending):
        patches = [patch.object(module, "_pending", return_value=pending),
                   patch.object(module, "_index_metadata", return_value={}),
                   patch.object(module, "_sync_last", return_value={})]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        panel = module.KnowledgeRemovalReviewPanel()
        panel.set_project_files("demo", ["b.py"])
        self.addCleanup(panel.close)
        return panel

    def wait(self, panel):
        for _ in range(200):
            self.app.processEvents()
            if not panel._busy:
                return
            time.sleep(0.01)
        self.fail("painel ocupado")

    def test_keep_button_commits_and_hides(self):
        panel = self.make_panel({"transaction": TX, "kind": "REMOVE", "removed_files": ["a.py"]})
        self.assertFalse(panel.banner.isHidden())
        self.assertIn("a.py", panel.banner_text.text())
        self.assertTrue(panel.keep_button.isEnabled())
        with patch.object(module, "_keep", return_value={"state": "COMMITTED"}) as keep:
            panel.request_keep()
            self.wait(panel)
            panel._drain_events()
        keep.assert_called_once_with(TX)
        self.assertIsNone(panel._undo_transaction)
        self.assertTrue(panel.keep_button.isHidden())
        self.assertIn("mantida", panel.banner_text.text())

    def test_merge_pending_does_not_show_removal_banner(self):
        panel = self.make_panel({"transaction": TX, "kind": "ADD"})
        self.assertTrue(panel.banner.isHidden())
        self.assertIsNone(panel._undo_transaction)

    def test_undo_of_auto_sync_switches_to_manual(self):
        panel = self.make_panel({"transaction": TX, "kind": "REMOVE"})
        saved = {}

        class Sync:
            def settings(self, project_id):
                return {"mode": "AUTO", "last": {"transaction": TX}}

            def update_settings(self, project_id, **changes):
                saved.update(changes)

        with patch.object(module, "_rollback", return_value={"state": "LAB_ROLLBACK_COMPLETE"}), \
             patch.object(module, "_sync_module", return_value=Sync()):
            panel.request_undo()
            self.wait(panel)
            panel._drain_events()
        self.assertEqual(saved, {"last": None, "mode": "MANUAL"})
        self.assertIn("Manual", panel.banner_text.text())


if __name__ == "__main__":
    unittest.main()