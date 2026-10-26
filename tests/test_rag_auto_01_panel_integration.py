"""RAG-AUTO-01 Qt integration: source consent and dashboard panel (offscreen)."""
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication,QMessageBox

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/"app_rewrite"))
import rag_panel
from rag.runtime import auto_index_api
from rag.runtime.auto_index_queue import get_job,list_jobs


class RagAutoPanelIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt=QApplication.instance() or QApplication([])

    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home=Path(tmp.name)
        self.root=self.home/"sources"
        self.root.mkdir()
        (self.root/"main.py").write_text("def active():\n  return 7\n",encoding="utf-8")
        (self.root/"README.md").write_text("Auto RAG project\n",encoding="utf-8")
        self.db=self.home/"auto"/"jobs"/"auto_index_jobs.sqlite3"
        path_patch=patch.object(auto_index_api,"default_queue_path",return_value=self.db)
        path_patch.start()
        self.addCleanup(path_patch.stop)
        with patch.object(rag_panel.RagPanel,"refresh",return_value=None):
            self.panel=rag_panel.RagPanel()
        self.addCleanup(self.panel.close)
        self.panel.project_id="integration-project"
        self.panel.auto_card.queue_path=self.db
        self.panel.auto_card.set_project("integration-project")
        self.panel.folder.setText(str(self.root))

        def run_synchronously(operation,args):
            try:
                result=rag_panel._rag_operation(operation,args)
            except Exception as exc:
                self.panel._complete(operation,{},str(exc))
            else:
                self.panel._complete(operation,result,"")
        self.panel._run=run_synchronously

    def test_new_tab_and_empty_dashboard(self):
        self.assertEqual(self.panel.pages.count(),4)
        self.assertEqual(self.panel.nav_buttons[3].text(),"Indexação automática")
        self.panel.set_page(3)
        self.assertEqual(self.panel.auto_card.percent.text(),"--%")
        self.assertFalse(self.db.exists())

    def test_preflight_then_explicit_queue_with_real_controls(self):
        self.panel.prepare_auto_job()
        self.assertIsNotNone(self.panel._auto_manifest)
        self.assertEqual(self.panel._auto_manifest["candidate_count"],2)
        self.assertTrue(self.panel.auto_authorize_btn.isEnabled())
        self.assertFalse(self.db.exists())
        with patch.object(QMessageBox,"question",return_value=QMessageBox.Yes):
            self.panel.authorize_auto_job()
        self.assertTrue(self.db.exists())
        jobs=list_jobs(self.db,project_id="integration-project")
        self.assertEqual(len(jobs),1)
        self.assertEqual(jobs[0]["state"],"QUEUED")
        self.assertEqual(self.panel.pages.currentIndex(),3)
        self.assertEqual(self.panel.auto_card.status.text(),"Aguardando executor")
        self.assertEqual(self.panel.auto_card.percent.text(),"--%")
        self.panel.auto_card.pause_button.click()
        self.assertEqual(get_job(self.db,jobs[0]["job_id"])["state"],"PAUSED")
        self.panel.auto_card.pause_button.click()
        self.assertEqual(get_job(self.db,jobs[0]["job_id"])["state"],"QUEUED")

    def test_declining_confirmation_does_not_create_queue(self):
        self.panel.prepare_auto_job()
        with patch.object(QMessageBox,"question",return_value=QMessageBox.No):
            self.panel.authorize_auto_job()
        self.assertFalse(self.db.exists())
        self.assertIsNotNone(self.panel._auto_manifest)

    def test_modified_source_cannot_be_authorized(self):
        self.panel.prepare_auto_job()
        (self.root/"main.py").write_text("print('modified')\n",encoding="utf-8")
        with patch.object(QMessageBox,"question",return_value=QMessageBox.Yes):
            self.panel.authorize_auto_job()
        self.assertFalse(self.db.exists())
        self.assertIsNone(self.panel._auto_manifest)

    def test_cancel_preview_discards_existing_digest(self):
        self.panel.prepare_auto_job()
        self.panel.cancel_preview()
        self.assertIsNone(self.panel._auto_manifest)
        self.assertFalse(self.panel.auto_authorize_btn.isEnabled())
        self.assertFalse(self.db.exists())

    def test_queued_signal_after_graceful_close_is_ignored(self):
        # Capture the real _run worker without launching a thread.
        self.panel._busy=False
        with patch.object(rag_panel.threading,"Thread") as thread_factory:
            rag_panel.RagPanel._run(self.panel,"auto_preview",{
                "project":"integration-project","root":str(self.root),
            })
            callback=thread_factory.call_args.kwargs["target"]
        self.panel._worker.deleteLater()
        self.qt.processEvents()
        # The QObject is already gone; no second emission or traceback.
        callback()
        self.assertFalse(self.db.exists())


if __name__=="__main__":
    unittest.main()
