import tempfile
import unittest
import sqlite3
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from rag.runtime.incremental_installed_queue_bootstrap_preflight import inspect_installed_queue_bootstrap
from rag.runtime.incremental_job_queue import _connection


class InstalledQueueBootstrapPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "CodeBridge" / "rag"
        self.root.mkdir(parents=True)
        self.sqlite = self.root / "rag_index.sqlite3"
        self.sqlite.write_bytes(b"legacy synthetic")
        self.jobs = self.root / "jobs"
        self.queue = self.jobs / "incremental_jobs.sqlite3"
        self.version = "v1_delta_1ae1d01ea84f4e"
        selected = self.root / "generations" / self.version
        selected.mkdir(parents=True)
        (selected / "rag_index.sqlite3").write_bytes(b"synthetic")
        (selected / "rag-index-manifest.json").write_text("{}", encoding="utf-8")
        self.pointer = {"state": "PUBLIC_POINTER_OBSERVED", "generation": self.version}

    def observe(self, *, pointer=None):
        with patch(
            "rag.runtime.incremental_installed_queue_bootstrap_preflight.resolve_rag_sqlite_path",
            return_value=self.sqlite,
        ), patch(
            "rag.runtime.incremental_installed_queue_bootstrap_preflight.inspect_public_pointer_for_scheduler",
            return_value=self.pointer if pointer is None else pointer,
        ):
            return inspect_installed_queue_bootstrap()

    def test_no_jobs_directory_remains_absent_after_inspection(self):
        report = self.observe()
        self.assertEqual(report["blockers"], ["QUEUE_DIRECTORY_BOOTSTRAP_PENDING"])
        self.assertFalse(report["directory_present"])
        self.assertFalse(report["permission_to_bootstrap"])
        self.assertFalse(self.jobs.exists())
        self.assertFalse(report["worker_started"])

    def test_existing_empty_directory_requires_schema(self):
        self.jobs.mkdir()
        report = self.observe()
        self.assertEqual(report["blockers"], ["QUEUE_SCHEMA_BOOTSTRAP_PENDING"])
        self.assertFalse(self.queue.exists())

    def test_existing_valid_queue_observed_but_no_permission_to_run(self):
        self.jobs.mkdir()
        with closing(_connection(self.queue, create=True)):
            pass
        report = self.observe()
        self.assertEqual(report["state"], "EXISTING_QUEUE_OBSERVED_ONLY")
        self.assertFalse(report["permission_to_bootstrap"])
        self.assertTrue(report["queue_present"])
        self.assertFalse(report["scheduler_started"])

    def test_corrupt_foreign_db_is_rejected_without_writing(self):
        self.jobs.mkdir()
        with closing(sqlite3.connect(self.queue)) as connection:
            connection.execute("CREATE TABLE foreign_t(data TEXT)")
            connection.execute("INSERT INTO foreign_t VALUES ('keep')")
            connection.commit()
        size = self.queue.stat().st_size
        report = self.observe()
        self.assertIn("EXISTING_QUEUE_UNVERIFIED", report["blockers"])
        self.assertEqual(self.queue.stat().st_size, size)
        with closing(sqlite3.connect(self.queue)) as connection:
            self.assertEqual(connection.execute("SELECT data FROM foreign_t").fetchone()[0], "keep")

    def test_previous_queue_schema_is_not_mistaken_for_ready(self):
        self.jobs.mkdir()
        with closing(_connection(self.queue, create=True)):
            pass
        with closing(sqlite3.connect(self.queue)) as connection:
            connection.execute("PRAGMA user_version=1")
            connection.commit()
        result = self.observe()
        self.assertIn("QUEUE_SCHEMA_UPGRADE_REQUIRED", result["blockers"])
        self.assertFalse(result["permission_to_bootstrap"])

    def test_pointer_change_mid_inspection_denies(self):
        before = self.pointer
        after = {"state": "PUBLIC_LEGACY_POINTER", "generation": "legacy"}
        with patch(
            "rag.runtime.incremental_installed_queue_bootstrap_preflight.resolve_rag_sqlite_path",
            return_value=self.sqlite,
        ), patch(
            "rag.runtime.incremental_installed_queue_bootstrap_preflight.inspect_public_pointer_for_scheduler",
            side_effect=[before, after],
        ):
            result = inspect_installed_queue_bootstrap()
        self.assertIn("PUBLIC_POINTER_CHANGED_DURING_INSPECTION", result["blockers"])

    def test_pending_public_transition_denies(self):
        (self.root / "production-generation-transition.json").write_text("{}")
        report = self.observe()
        self.assertIn("PUBLIC_TRANSITION_PENDING", report["blockers"])
        self.assertFalse(self.jobs.exists())

    def test_unverified_public_generation_denies(self):
        report = self.observe(pointer={"state": "PUBLIC_POINTER_INVALID"})
        self.assertIn("PUBLIC_GENERATION_NOT_VERIFIED", report["blockers"])
        self.assertFalse(self.jobs.exists())


if __name__ == "__main__":
    unittest.main()
