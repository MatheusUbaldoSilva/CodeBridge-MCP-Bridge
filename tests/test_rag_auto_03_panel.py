"""RAG-AUTO-03 Qt intents for candidate preparation and reversible canary."""
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication,QMessageBox
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"app_rewrite"))
from rag_panel import RagPanel


class Auto03PanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt=QApplication.instance() or QApplication([])

    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        with patch.object(RagPanel,"refresh",return_value=None):
            self.panel=RagPanel()
        self.addCleanup(self.panel.close)
        self.panel.project_id="project-demo"
        self.job="a"*32

    def test_card_has_real_separate_canary_controls(self):
        card=self.panel.auto_card
        self.assertEqual(card.prepare_button.text(),"Preparar versão")
        self.assertIn("leitura",card.enable_button.text())
        self.assertIn("Reverter",card.rollback_button.text())
        self.assertFalse(card.enable_button.isEnabled())

    def test_gui_requests_need_confirmed_project_job(self):
        with (
            patch("rag.runtime.auto_index_queue.default_queue_path",return_value=self.root),
            patch("rag.runtime.auto_index_queue.get_job",
                  return_value={"job_id":self.job,"project_id":"project-demo"}),
            patch.object(self.panel,"_run") as operation,
            patch.object(QMessageBox,"question",return_value=QMessageBox.Yes),
        ):
            self.panel.auto_card.prepare_requested.emit(self.job)
            self.panel.auto_card.enable_requested.emit(self.job)
            self.panel.auto_card.rollback_requested.emit(self.job)
        self.assertEqual(operation.call_count,3)
        args=[call.args for call in operation.call_args_list]
        self.assertEqual(
            [x[0] for x in args],
            ["auto_prepare_generation","auto_enable_canary","auto_rollback_canary"],
        )
        self.assertEqual(
            args[0][1]["confirmation"],
            "RAG_AUTO_PREPARE:project-demo:"+self.job,
        )

    def test_declining_confirmation_does_not_change_state(self):
        with (
            patch("rag.runtime.auto_index_queue.default_queue_path",return_value=self.root),
            patch("rag.runtime.auto_index_queue.get_job",
                  return_value={"job_id":self.job,"project_id":"project-demo"}),
            patch.object(self.panel,"_run") as operation,
            patch.object(QMessageBox,"question",return_value=QMessageBox.No),
        ):
            self.panel._enable_canary(self.job)
        operation.assert_not_called()


if __name__=="__main__":
    unittest.main()
