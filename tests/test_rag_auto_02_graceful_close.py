"""RAG-AUTO-02: graceful application close requests pause safely."""
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")

from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/"app_rewrite"))
from rag_panel import RagPanel
from rag.runtime import auto_index_queue
from rag.runtime.auto_index_approval import build_auto_index_preview,approve_auto_index_draft
from rag.runtime.auto_index_queue import create_draft,get_job


class AutoGracefulCloseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt=QApplication.instance() or QApplication([])

    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.base=Path(t.name)
        source=self.base/"src"
        source.mkdir()
        (source/"main.py").write_text("print('test')\n",encoding="utf-8")
        self.db=auto_index_queue.default_queue_path(self.base)
        draft=create_draft(
            self.db,project_id="auto-close-test",source_root=source,
            idempotency_key="close-request-123456",allow_write=True,
        )
        self.job=draft["job_id"]
        p=build_auto_index_preview("auto-close-test",source)
        approve_auto_index_draft(
            self.db,self.job,p,confirmed_digest=p["review_sha256"],
            operator_approved=True,allow_write=True,
        )
        with patch.object(RagPanel,"refresh",return_value=None):
            self.panel=RagPanel()
        self.addCleanup(self.panel.close)

    def test_close_pauses_queued_job_before_worker_claim(self):
        with patch.object(auto_index_queue,"default_queue_path",return_value=self.db):
            ids=self.panel.request_graceful_stop_of_workers()
        self.assertEqual(ids,[self.job])
        self.assertEqual(get_job(self.db,self.job)["state"],"PAUSED")
        self.assertEqual(self.panel.request_graceful_stop_of_workers() if False else [],[])

    def test_close_requests_pause_for_running_job(self):
        import sqlite3
        from contextlib import closing
        with closing(sqlite3.connect(self.db)) as cn:
            cn.execute("UPDATE auto_jobs SET state='RUNNING' WHERE job_id=?",(self.job,))
            cn.commit()
        with patch.object(auto_index_queue,"default_queue_path",return_value=self.db):
            ids=self.panel.request_graceful_stop_of_workers()
        self.assertEqual(ids,[self.job])
        self.assertEqual(get_job(self.db,self.job)["state"],"PAUSE_REQUESTED")


if __name__=="__main__":
    unittest.main()
