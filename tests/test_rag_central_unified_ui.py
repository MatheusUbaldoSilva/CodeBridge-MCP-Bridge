import os
import sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app_rewrite"))
from PySide6.QtWidgets import QApplication  # noqa: E402
import rag_deletion_review_panel as module  # noqa: E402
from rag_deletion_review_panel import KnowledgeRemovalReviewPanel, RemovalConfirmDialog  # noqa: E402

GENUINE = {
    "state": "READ_ONLY_REVIEW", "project_id": "demo", "selected_paths": ["src/a.py"],
    "review_sha256": "a" * 64, "execution_enabled": False, "documents_to_remove": 1,
    "chunks_to_remove": 3, "documents_to_preserve": 2,
    "display_text": "SIMULAÇÃO: nenhum conhecimento foi removido.",
}


class UnifiedCentralRagTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        patcher = patch.object(module, "_pending", return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)
        meta = patch.object(module, "_index_metadata",
                            return_value={"src/a.py": (3, 2048), "src/b.py": (1, 10), "README.md": (2, 0)})
        meta.start()
        self.addCleanup(meta.stop)
        self.panel = KnowledgeRemovalReviewPanel()
        self.addCleanup(self.panel.close)
        self.panel.set_project_files("demo", ["src/a.py", "src/b.py", "README.md"],
                                     [{"path": "src/a.py", "type": "CODE"}])

    def test_tree_groups_folders_and_counts_chunks(self):
        tree = self.panel.selector.tree
        self.assertEqual(self.panel.selector.leaf_count(), 3)
        folder = [tree.topLevelItem(i) for i in range(tree.topLevelItemCount())
                  if tree.topLevelItem(i).text(0) == "src/"][0]
        self.assertEqual(folder.childCount(), 2)
        self.assertEqual(folder.text(2), "4")
        self.assertIn("6 chunks", self.panel.selector.totals.text())

    def test_filter_hides_non_matching_files(self):
        self.panel.selector.filter.setText("readme")
        leaves = self.panel.selector._leaves
        self.assertFalse(leaves["README.md"].isHidden())
        self.assertTrue(leaves["src/a.py"].isHidden())

    def test_selection_drives_footer_and_clear(self):
        self.assertFalse(self.panel.delete_button.isEnabled())
        self.panel.selector.set_checked("src/a.py")
        self.assertTrue(self.panel.delete_button.isEnabled())
        self.assertIn("1 selecionado", self.panel.delete_status.text())
        self.assertIn("3 chunks", self.panel.delete_status.text())
        self.panel.selector.clear_checks()
        self.assertEqual(self.panel.selector.selected_paths(), [])
        self.assertFalse(self.panel.delete_button.isEnabled())

    def test_confirm_dialog_requires_exact_project_name(self):
        dialog = RemovalConfirmDialog("demo", GENUINE)
        self.addCleanup(dialog.close)
        self.assertFalse(dialog.ok.isEnabled())
        dialog.name.setText("dem")
        self.assertFalse(dialog.ok.isEnabled())
        dialog.name.setText("demo")
        self.assertTrue(dialog.ok.isEnabled())

    def test_cancelled_dialog_never_executes(self):
        self.panel.selector.set_checked("src/a.py")
        with patch.object(module, "build_deletion_review", return_value=dict(GENUINE)), \
                patch.object(module.RemovalConfirmDialog, "exec", return_value=0), \
                patch.object(module, "_execute") as execute:
            self.panel.request_removal()
        execute.assert_not_called()

    def test_successful_removal_updates_tree_banner_and_undo(self):
        self.panel.selector.set_checked("src/a.py")
        result = {"removed_files": ["src/a.py"], "transaction": "t1", "documents_removed": 1,
                  "chunks_removed": 3, "previous_generation": "g1", "generation": "g2"}
        with patch.object(module, "build_deletion_review", return_value=dict(GENUINE)), \
                patch.object(module.RemovalConfirmDialog, "exec", return_value=1), \
                patch.object(module.RemovalConfirmDialog, "confirmation", return_value="demo"), \
                patch.object(module, "_execute", return_value=result) as execute, \
                patch("threading.Thread") as thread:
            thread.return_value.start.side_effect = lambda: thread.call_args.kwargs["target"]()
            self.panel.request_removal()
            self.panel._drain_events()
        execute.assert_called_once()
        self.assertEqual(execute.call_args.args[:4], ("demo", ["src/a.py"], "a" * 64, "demo"))
        self.assertNotIn("src/a.py", self.panel.selector._leaves)
        self.assertFalse(self.panel.banner.isHidden())
        self.assertIn("removido", self.panel.banner_text.text())
        self.assertTrue(self.panel.undo_button.isEnabled())

    def test_public_project_never_enables_delete(self):
        self.panel.set_project_files("codebridge", ["README.md"])
        self.panel.selector.set_checked("README.md")
        self.assertFalse(self.panel.delete_button.isEnabled())