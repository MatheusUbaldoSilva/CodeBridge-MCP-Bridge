"""RAG-AUTO-01.6 telemetry has no simulated progress or worker side-effects."""
from pathlib import Path
import tempfile
import unittest

from rag.runtime.auto_index_queue import create_draft,default_queue_path,latest_event,list_events,inspect_queue_operational,preferred_display_job
from rag.runtime.auto_index_telemetry import (
    inspect_auto_index_dashboard,read_auto_index_job_status,
)


class AutoIndexTelemetryTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)/"project"
        self.root.mkdir()
        (self.root/"main.py").write_text("print(1)\n",encoding="utf-8")
        self.db=default_queue_path(Path(tmp.name))

    def test_missing_store_creates_nothing(self):
        snapshot=inspect_auto_index_dashboard(self.db)
        self.assertEqual(snapshot["jobs"],[])
        self.assertEqual(snapshot["queue"]["state"],"NOT_INITIALIZED")
        self.assertFalse(self.db.exists())

    def test_preferred_display_job_is_read_only_and_validates_namespace(self):
        self.assertIsNone(preferred_display_job(self.db,'example'))
        self.assertFalse(self.db.exists())
        with self.assertRaises(ValueError):
            preferred_display_job(self.db,'../outside')

    def test_operational_queue_read_skips_expensive_integrity_check(self):
        self.assertEqual(inspect_queue_operational(self.db)['state'],'NOT_INITIALIZED')
        self.assertFalse(self.db.exists())
        create_draft(self.db,project_id='example',source_root=self.root,
                     idempotency_key='telemetry-fast-queue-001',allow_write=True)
        from unittest.mock import patch
        with patch('rag.runtime.auto_index_queue.inspect_queue',side_effect=AssertionError('full scan')):
            state=inspect_queue_operational(self.db)
        self.assertEqual(state['jobs'],1)
        self.assertEqual(state['by_state']['DRAFT'],1)

    def test_draft_progress_is_unknown_not_fake_percentage(self):
        job=create_draft(
            self.db,project_id="example",source_root=self.root,
            idempotency_key="telemetry-123456789",allow_write=True,
        )
        result=read_auto_index_job_status(self.db,job["job_id"])
        self.assertIsNone(result["percent"])
        self.assertFalse(result["percent_known"])
        self.assertEqual(result["vectors_done"],0)
        self.assertEqual(result["last_event"],"DRAFT_CREATED")
        self.assertFalse(result["worker_started_by_status_read"])
        self.assertFalse(result["publication_authorized"])
        jobs=inspect_auto_index_dashboard(self.db)["jobs"]
        self.assertEqual(jobs[0]["job_id"],job["job_id"])

    def test_latest_event_matches_history_without_creating_missing_store(self):
        self.assertIsNone(latest_event(self.db,'a'*32))
        self.assertFalse(self.db.exists())
        job=create_draft(
            self.db,project_id='example',source_root=self.root,
            idempotency_key='telemetry-latest-1234',allow_write=True,
        )
        events=list_events(self.db,job['job_id'])
        self.assertEqual(latest_event(self.db,job['job_id']),events[-1])
        self.assertIsNone(latest_event(self.db,'b'*32))
        with self.assertRaises(ValueError):
            latest_event(self.db,'invalid')

    def test_expired_or_foreign_lease_is_not_reported_as_reserved(self):
        from unittest.mock import patch
        job=create_draft(
            self.db,project_id='example',source_root=self.root,
            idempotency_key='telemetry-lease-check-123',allow_write=True,
        )
        base={'state':'LEASE_RECORDED','job_id':job['job_id'],'lease_until_epoch':10.0}
        with patch('rag.runtime.auto_index_telemetry.inspect_index_supervisor',return_value=base), patch('rag.runtime.auto_index_telemetry.time.time',return_value=20.0):
            status=read_auto_index_job_status(self.db,job['job_id'])
            self.assertFalse(status['supervisor_reserved'])
            self.assertTrue(status['supervisor_lease_expired'])
        with patch('rag.runtime.auto_index_telemetry.inspect_index_supervisor',return_value={**base,'lease_until_epoch':30.0}), patch('rag.runtime.auto_index_telemetry.time.time',return_value=20.0):
            self.assertTrue(read_auto_index_job_status(self.db,job['job_id'])['supervisor_reserved'])
        with patch('rag.runtime.auto_index_telemetry.inspect_index_supervisor',return_value={**base,'job_id':'0'*32,'lease_until_epoch':30.0}), patch('rag.runtime.auto_index_telemetry.time.time',return_value=20.0):
            self.assertFalse(read_auto_index_job_status(self.db,job['job_id'])['supervisor_reserved'])

    def test_does_not_start_models_during_optional_probe(self):
        job=create_draft(
            self.db,project_id="example",source_root=self.root,
            idempotency_key="telemetry-123456789",allow_write=True,
        )
        from unittest.mock import patch
        with patch("rag.runtime.auto_index_telemetry._probe_system_resources",
                   return_value=({"free_mib":2200,"total_mib":8192},None)) as probe:
            status=read_auto_index_job_status(
                self.db,job["job_id"],probe_resources=True,
            )
        self.assertEqual(status["memory"]["free_mib"],2200)
        self.assertFalse(status["worker_started_by_status_read"])
        probe.assert_called_once()


if __name__=="__main__":
    unittest.main()
