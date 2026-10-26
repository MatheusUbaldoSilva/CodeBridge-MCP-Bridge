"""RAG-AUTO-01.7 Qt progress card tests, entirely offscreen."""
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")

from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication,QMessageBox

from rag.runtime.auto_index_queue import create_draft,default_queue_path,get_job
from rag.runtime.auto_index_approval import (
    build_auto_index_preview,approve_auto_index_draft,
)

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"app_rewrite"))
from rag_auto_job_card import RagAutoJobCard


class RagAutoQtCardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt=QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)
        self.db=default_queue_path(self.base)
        self.root=self.base/"project"
        self.root.mkdir()
        (self.root/"main.py").write_text("print('ok')\n",encoding="utf-8")
        self.project="mockup-project"

    def card(self):
        card=RagAutoJobCard(queue_path=self.db,project_id=self.project)
        self.addCleanup(card.close)
        return card

    def job(self):
        draft=create_draft(
            self.db,project_id=self.project,source_root=self.root,
            idempotency_key="visual-card-request-1234",
            allow_write=True,
        )
        preview=build_auto_index_preview(self.project,self.root)
        approve_auto_index_draft(
            self.db,draft["job_id"],preview,
            confirmed_digest=preview["review_sha256"],
            operator_approved=True,allow_write=True,
        )
        return draft

    def test_no_fictional_progress_or_db_created(self):
        card=self.card()
        self.assertEqual(card.percent.text(),"--%")
        self.assertIn("Sem trabalho",card.status.text())
        self.assertFalse(card.pause_button.isEnabled())
        self.assertFalse(card.cancel_button.isEnabled())
        self.assertFalse(self.db.exists())

    def test_real_queued_job_not_falsely_indexing(self):
        self.job()
        card=self.card()
        self.assertEqual(card.status.text(),"Aguardando executor")
        self.assertEqual(card.percent.text(),"--%")
        self.assertEqual(card.bar.value(),0)
        self.assertIn("Iniciar indexação",card.detail.text())
        self.assertTrue(card.pause_button.isEnabled())

    def test_pause_and_resume_update_durable_job(self):
        job=self.job()
        card=self.card()
        card.pause_button.click()
        self.assertEqual(card.status.text(),"Pausado")
        self.assertEqual(get_job(self.db,job["job_id"])["state"],"PAUSED")
        card.pause_button.click()
        self.assertEqual(card.status.text(),"Aguardando executor")
        self.assertEqual(get_job(self.db,job["job_id"])["state"],"QUEUED")

    def test_cancel_requires_confirmation_and_records_it(self):
        job=self.job()
        card=self.card()
        with patch.object(QMessageBox,"question",return_value=QMessageBox.No):
            card.cancel_button.click()
        self.assertEqual(get_job(self.db,job["job_id"])["state"],"QUEUED")
        with patch.object(QMessageBox,"question",return_value=QMessageBox.Yes):
            card.cancel_button.click()
        self.assertEqual(get_job(self.db,job["job_id"])["state"],"CANCELLED")
        self.assertEqual(card.status.text(),"Cancelado")
        self.assertFalse(card.cancel_button.isEnabled())


if __name__=="__main__":
    unittest.main()
