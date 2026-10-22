import unittest
from pathlib import Path
from unittest.mock import patch

from rag.runtime.incremental_installed_scheduler_preflight import inspect_installed_scheduler_preflight


class InstalledSchedulerPreflightTests(unittest.TestCase):
    def test_missing_installed_queue_blocks_without_writes(self):
        with patch("rag.runtime.incremental_installed_scheduler_preflight.resolve_rag_sqlite_path",
                   return_value=Path("C:/CodeBridge/rag/rag_index.sqlite3")):
            result = inspect_installed_scheduler_preflight(
                queue_db=Path("C:/CodeBridge/rag/not-installed-queue.sqlite3"))
        self.assertEqual(result["state"], "AUTONOMOUS_SCHEDULING_BLOCKED")
        self.assertFalse(result["scheduler_started"])
        self.assertFalse(result["active_index_updated"])

    def test_reject_queue_escape(self):
        with patch("rag.runtime.incremental_installed_scheduler_preflight.resolve_rag_sqlite_path",
                   return_value=Path("C:/CodeBridge/rag/rag_index.sqlite3")):
            result = inspect_installed_scheduler_preflight(
                queue_db=Path("C:/unrelated/queue.sqlite3"))
        self.assertIn("QUEUE_PATH_OUTSIDE_INSTALLED_RAG", result["blockers"])
        self.assertFalse(result["activation_authorized"])


if __name__ == "__main__":
    unittest.main()
