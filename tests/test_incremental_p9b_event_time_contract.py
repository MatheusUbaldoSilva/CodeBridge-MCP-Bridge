"""P9-B: invalid event timing must be rejected before any database write."""
import tempfile
import unittest
from pathlib import Path

from rag.runtime.incremental_job_prequeue import assess_commit_index_event
from rag.runtime.incremental_job_queue import enqueue_source_event


class InvalidEventTimingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / "CodeBridge-MCP-Bridge"
        self.project.mkdir()
        (self.project / ".git").mkdir()
        (self.project / "sample.py").write_text("value = 7\n")
        self.queue = Path(self.temp.name) / "jobs" / "incremental_jobs.sqlite3"
        self.params = {
            "approved_paths": ("sample.py",),
            "observed_commit": "a" * 40,
            "observed_sha256": "b" * 64,
            "changed_at_epoch": 100,
            "debounce_seconds": 30,
            "now_epoch": 140,
        }

    def test_non_finite_and_invalid_numeric_event_values_fail_closed(self):
        cases = (
            ("changed_at_epoch", float("nan")),
            ("changed_at_epoch", float("inf")),
            ("changed_at_epoch", -float("inf")),
            ("changed_at_epoch", "100"),
            ("changed_at_epoch", True),
            ("debounce_seconds", float("nan")),
            ("debounce_seconds", float("inf")),
            ("debounce_seconds", "30"),
            ("debounce_seconds", False),
            ("now_epoch", float("nan")),
            ("now_epoch", float("inf")),
            ("now_epoch", "140"),
            ("now_epoch", True),
        )
        for key, invalid in cases:
            with self.subTest(field=key, invalid=str(invalid)):
                params = dict(self.params)
                params[key] = invalid
                event = assess_commit_index_event(
                    self.project, "sample.py", indexing_enabled=True, **params,
                )
                self.assertEqual(event["state"], "INVALID_STABILITY_CONTRACT")
                queued = enqueue_source_event(
                    self.queue, self.project, "sample.py", queue_enabled=True, **params,
                )
                self.assertEqual(queued["state"], "INVALID_STABILITY_CONTRACT")
                self.assertFalse(self.queue.exists())

    def test_negative_or_reversed_times_denied(self):
        for params in ({"changed_at_epoch": -1},
                       {"debounce_seconds": 3601},
                       {"now_epoch": 90}):
            with self.subTest(params=params):
                event = assess_commit_index_event(
                    self.project, "sample.py", indexing_enabled=True,
                    **{**self.params, **params},
                )
                self.assertEqual(event["state"], "INVALID_STABILITY_CONTRACT")
                self.assertFalse(self.queue.exists())


if __name__ == "__main__":
    unittest.main()
