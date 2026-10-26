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

    def test_expanded_diagnostics_use_persisted_status(self):
        draft=self.job()
        card=self.card()
        self.assertFalse(card.diagnostics.isVisible())
        with patch.object(card,"_request_resource_sample"):
            card.details_toggle.click()
        self.assertIn(draft["job_id"],card.diagnostics.text())
        self.assertIn("TEXT: 0 vetores",card.diagnostics.text())
        self.assertIn("Aguardando executor",card.diagnostics.text())

    def test_resource_sample_is_presented_without_fake_values(self):
        self.job()
        card=self.card()
        with patch.object(card,"_request_resource_sample"):
            card.details_toggle.click()
        card._accept_resource_sample((
            {"free_mib":2048,"total_mib":8192},
            {"used_mib":1024,"total_mib":6144,"utilization_percent":27},
        ))
        self.assertIn("RAM livre: 2048 / 8192 MiB",card.diagnostics.text())
        self.assertIn("GPU: 1024 / 6144 MiB",card.diagnostics.text())

    def test_queue_health_is_read_only_and_reports_counts(self):
        card=self.card()
        self.assertIn("não inicializada",card.queue_health.text())
        self.assertFalse(self.db.exists())
        self.job()
        card._refresh_queue_health()
        self.assertIn("1 jobs",card.queue_health.text())
        self.assertIn("1 aguardando",card.queue_health.text())

    def test_fast_refresh_does_not_repeat_expensive_queue_integrity_scan(self):
        self.job()
        card=self.card()
        with patch('rag_auto_job_card.inspect_queue_operational',side_effect=AssertionError('unexpected queue scan')):
            card.refresh()
        self.assertEqual(card.status.text(),'Aguardando executor')
        self.assertEqual(card._queue_timer.interval(),30000)

    def test_expired_supervisor_reservation_is_diagnostic_only(self):
        self.job()
        card=self.card()
        with patch('rag.runtime.auto_index_supervisor.inspect_index_supervisor',return_value={
            'state':'LEASE_RECORDED','job_id':'other','lease_until_epoch':1.0,
        }), patch.object(card,'_request_resource_sample'):
            card.details_toggle.click()
        self.assertIn('reserva do supervisor expirada',card.diagnostics.text())

    def test_slow_resource_probe_does_not_block_qt_event_loop(self):
        import threading
        ready=threading.Event()
        release=threading.Event()
        self.job()
        card=self.card()
        def slow_probe():
            ready.set()
            release.wait(timeout=2)
            return ({'free_mib':3333,'total_mib':8192},None)
        with patch('rag.runtime.auto_index_telemetry._probe_system_resources',side_effect=slow_probe):
            try:
                card.details_toggle.click()
                self.assertTrue(ready.wait(timeout=1))
                self.assertTrue(card._resource_busy)
                self.qt.processEvents()
                self.assertTrue(card.details_toggle.isChecked())
            finally:
                release.set()
            import time
            deadline=time.monotonic()+2
            while card._resource_busy and time.monotonic()<deadline:
                self.qt.processEvents()
                time.sleep(.01)
        self.assertFalse(card._resource_busy)
        self.assertIn('RAM livre: 3333',card.diagnostics.text())

    def test_resource_probe_failure_does_not_claim_memory_values(self):
        self.job()
        card=self.card()
        with patch.object(card,'_request_resource_sample'):
            card.details_toggle.click()
        with patch('rag.runtime.auto_index_telemetry._probe_system_resources',side_effect=RuntimeError('probe unavailable')):
            card._sample_resources()
            self.qt.processEvents()
        self.assertNotIn('RAM livre:',card.diagnostics.text())
        self.assertNotIn('GPU:',card.diagnostics.text())
        self.assertFalse(card._resource_busy)

    def test_active_job_is_not_hidden_by_newer_draft(self):
        import sqlite3
        from contextlib import closing
        old=self.job()
        with closing(sqlite3.connect(self.db)) as cn:
            cn.execute("UPDATE auto_jobs SET state='RUNNING' WHERE job_id=?",(old['job_id'],))
            cn.commit()
        recent=create_draft(self.db,project_id=self.project,source_root=self.root,
                            idempotency_key='second-draft-request-9876',allow_write=True)
        card=self.card()
        self.assertEqual(card._job_id,old['job_id'])
        self.assertEqual(card.status.text(),'Indexando')
        self.assertEqual(get_job(self.db,recent['job_id'])['state'],'DRAFT')

    def test_history_keeps_older_active_job_visible(self):
        import sqlite3
        from contextlib import closing
        first=self.job()
        with closing(sqlite3.connect(self.db)) as cn:
            cn.execute("UPDATE auto_jobs SET state='RUNNING' WHERE job_id=?",(first['job_id'],))
            cn.commit()
        for number in range(11):
            create_draft(self.db,project_id=self.project,source_root=self.root,
                         idempotency_key=f'later-draft-{number:02d}-abcdefgh',allow_write=True)
        card=self.card()
        card.history_toggle.click()
        self.assertIn(first['job_id'][:12],card.history_label.text())
        self.assertEqual(card._job_id,first['job_id'])

    def test_history_shows_real_jobs_without_mutation(self):
        draft=self.job()
        card=self.card()
        card.history_toggle.click()
        self.assertIn(draft["job_id"][:12],card.history_label.text())
        self.assertIn("Aguardando executor",card.history_label.text())
        self.assertEqual(get_job(self.db,draft["job_id"])["state"],"QUEUED")

    def test_pause_and_resume_update_durable_job(self):
        job=self.job()
        card=self.card()
        card.pause_button.click()
        self.assertEqual(card.status.text(),"Pausado")
        self.assertEqual(get_job(self.db,job["job_id"])["state"],"PAUSED")
        card.pause_button.click()
        self.assertEqual(card.status.text(),"Aguardando executor")
        self.assertEqual(get_job(self.db,job["job_id"])["state"],"QUEUED")

    def test_expired_worker_lease_alert_is_read_only(self):
        self.job()
        card=self.card()
        card._render({**card._status,'state':'RUNNING','supervisor_lease_expired':True})
        self.assertIn('Reserva do worker expirada',card.alert.text())
        card._render({**card._status,'state':'READY_FOR_REVIEW','supervisor_lease_expired':True})
        self.assertNotIn('Reserva do worker expirada',card.alert.text())

    def test_alert_tracks_persisted_pause_request_state(self):
        self.job()
        card=self.card()
        self.assertFalse(card.alert.isVisible())
        card._render({**card._status,"state":"PAUSE_REQUESTED"})
        self.assertIn("Pausa solicitada",card.alert.text())
        card._render({**card._status,"state":"QUEUED"})
        self.assertEqual(card.alert.text(),"")

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
