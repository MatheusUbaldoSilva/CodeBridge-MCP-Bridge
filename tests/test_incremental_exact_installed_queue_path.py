import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rag.runtime.incremental_installed_scheduler_preflight import inspect_installed_scheduler_preflight


class ExactInstalledQueuePathTests(unittest.TestCase):
    def test_nested_jobs_directory_must_be_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "CodeBridge" / "rag"
            root.mkdir(parents=True)
            nested = root / "other" / "jobs" / "incremental_jobs.sqlite3"
            with patch(
                "rag.runtime.incremental_installed_scheduler_preflight.resolve_rag_sqlite_path",
                return_value=root / "rag_index.sqlite3",
            ):
                report = inspect_installed_scheduler_preflight(queue_db=nested)
        self.assertEqual(report["blockers"], ["QUEUE_PATH_OUTSIDE_INSTALLED_RAG"])
        self.assertFalse(report["activation_authorized"])
        self.assertFalse(report["worker_started"])

    def test_canonical_installed_location_reaches_diagnostic(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "CodeBridge" / "rag"
            root.mkdir(parents=True)
            with patch(
                "rag.runtime.incremental_installed_scheduler_preflight.resolve_rag_sqlite_path",
                return_value=root / "rag_index.sqlite3",
            ):
                report = inspect_installed_scheduler_preflight(
                    queue_db=root / "jobs" / "incremental_jobs.sqlite3",
                )
        self.assertNotIn("QUEUE_PATH_OUTSIDE_INSTALLED_RAG", report["blockers"])
        self.assertFalse(report["scheduler_started"])


if __name__ == "__main__":
    unittest.main()
