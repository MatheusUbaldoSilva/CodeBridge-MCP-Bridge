import unittest
from pathlib import Path
from unittest.mock import patch
from rag.runtime.incremental_installed_scheduler_preflight import inspect_installed_scheduler_preflight


class InstalledPathContractTests(unittest.TestCase):
    def test_default_path_uses_dedicated_jobs_directory(self):
        with patch(
            "rag.runtime.incremental_installed_scheduler_preflight.resolve_rag_sqlite_path",
            return_value=Path("C:/CodeBridge/rag/rag_index.sqlite3"),
        ):
            report = inspect_installed_scheduler_preflight()
        self.assertTrue(report["queue_db"].replace("\\", "/").endswith(
            "/rag/jobs/incremental_jobs.sqlite3"
        ))
        self.assertEqual(report["mode"], "READ_ONLY_PREFLIGHT")
        self.assertFalse(report["activation_authorized"])
        self.assertFalse(report["active_index_updated"])

    def test_foreign_database_filename_is_rejected(self):
        with patch(
            "rag.runtime.incremental_installed_scheduler_preflight.resolve_rag_sqlite_path",
            return_value=Path("C:/CodeBridge/rag/rag_index.sqlite3"),
        ):
            report = inspect_installed_scheduler_preflight(
                queue_db=Path("C:/CodeBridge/rag/jobs/unrelated.sqlite3"),
            )
        self.assertIn("QUEUE_PATH_OUTSIDE_INSTALLED_RAG", report["blockers"])
        self.assertFalse(report["worker_started"])


if __name__ == "__main__":
    unittest.main()
