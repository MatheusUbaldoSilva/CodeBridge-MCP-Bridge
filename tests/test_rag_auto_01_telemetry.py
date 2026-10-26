"""RAG-AUTO-01.6 telemetry has no simulated progress or worker side-effects."""
from pathlib import Path
import tempfile
import unittest

from rag.runtime.auto_index_queue import create_draft,default_queue_path
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
