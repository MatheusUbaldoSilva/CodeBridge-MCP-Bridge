"""RAG-DEL-01.04-DN: Qt document list remains fail-closed on pin errors."""
import os
import sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app_rewrite"))
from PySide6.QtWidgets import QApplication
from rag_panel import RagPanel


class DocumentFailureQtTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.patch=patch.object(RagPanel,"refresh",return_value=None)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.panel=RagPanel()
        self.addCleanup(self.panel.close)

    def test_cutover_busy_preserves_current_public_read_only_selection(self):
        self.panel.project_id="codebridge"
        docs=[{"path":"README.md","count":1,"type":"DOCUMENTATION"}]
        self.panel._complete("documents",docs,"")
        before=list(self.panel._documents)
        self.panel._complete("documents",{}, "generation busy")
        self.assertEqual(self.panel._documents,before)
        self.assertEqual(self.panel.files.count(),1)
        self.assertIn("generation busy",self.panel.notice.text())
        self.assertFalse(self.panel.deletion_review_panel.delete_button.isEnabled())

    def test_private_project_switch_clears_public_files_before_request(self):
        self.panel.project_id="codebridge"
        self.panel._complete("documents",[
            {"path":"README.md","count":1,"type":"DOCUMENTATION"},
        ],"")
        with patch.object(self.panel,"_run") as dispatch:
            self.panel.change_project("private-demo")
        self.assertEqual(self.panel.project_id,"private-demo")
        self.assertEqual(self.panel.files.count(),0)
        self.assertEqual(self.panel._documents,[])
        dispatch.assert_called_once_with("documents",{"project":"private-demo"})
        self.panel._complete("documents",{},"catalog busy")
        self.assertEqual(self.panel.files.count(),0)
        self.assertFalse(self.panel.deletion_review_panel.delete_button.isEnabled())
        self.assertIn("catalog busy",self.panel.notice.text())

    def test_public_failed_request_does_not_set_delete_selection(self):
        self.panel.project_id="codebridge"
        self.panel._complete("documents",{}, "public generation transition pending")
        self.assertEqual(self.panel.deletion_review_panel.selector.selected_paths(),[])
        self.assertFalse(self.panel.deletion_review_panel.delete_button.isEnabled())