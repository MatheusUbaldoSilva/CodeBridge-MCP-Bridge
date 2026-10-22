"""Invalid offline worker heartbeats must refuse reservation before any SQLite writes."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from rag.runtime.incremental_offline_worker import process_offline_job_once


class OfflineHeartbeatBoundsTests(unittest.TestCase):
    def test_invalid_intervals_are_rejected_before_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue = root / "jobs" / "incremental_jobs.sqlite3"
            for value in (float("nan"), float("inf"), -float("inf"),
                          True, False, "30", 0.0, -1, 30.001, 10000):
                with self.subTest(value=str(value)), patch(
                    "rag.runtime.incremental_offline_worker.claim_approved_job",
                    side_effect=AssertionError("must not claim"),
                ):
                    state = process_offline_job_once(
                        queue, root, approved_paths=("sample.py",),
                        queue_enabled=True, worker_enabled=True,
                        heartbeat_interval_seconds=value,
                        builder=lambda _: {"state": "STAGED_NOT_PUBLISHED"},
                    )
                    self.assertEqual(state["state"], "INVALID_HEARTBEAT_POLICY")
                    self.assertFalse(state["active_index_updated"])
                    self.assertFalse(queue.exists())

    def test_disabled_worker_remains_inert_even_with_invalid_interval(self):
        with tempfile.TemporaryDirectory() as tmp:
            queue = Path(tmp) / "jobs" / "incremental_jobs.sqlite3"
            result = process_offline_job_once(
                queue, Path(tmp), heartbeat_interval_seconds=float("nan")
            )
            self.assertEqual(result["state"], "OFFLINE_WORKER_DISABLED")
            self.assertFalse(queue.exists())


if __name__ == "__main__":
    unittest.main()
