"""P9-B fail-closed numeric lease policy without touching installed SQLite."""
import tempfile
import unittest
from pathlib import Path

from rag.runtime.incremental_job_queue import (
    acknowledge_staged_bundle, claim_approved_job, renew_job_lease,
    report_staging_failure,
)


class InvalidLeaseTimingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.queue = Path(self.temp.name) / "jobs" / "incremental_jobs.sqlite3"
        self.project = Path(self.temp.name) / "CodeBridge-MCP-Bridge"
        self.job = "a" * 64
        self.token = "b" * 32

    def test_claim_rejects_non_finite_and_non_numeric_input(self):
        cases = (
            {"now_epoch": float("nan")},
            {"now_epoch": float("inf")},
            {"now_epoch": "140"},
            {"now_epoch": True},
            {"now_epoch": -1},
            {"lease_seconds": float("nan")},
            {"lease_seconds": float("inf")},
            {"lease_seconds": "120"},
            {"lease_seconds": True},
            {"max_attempts": True},
            {"max_attempts": 1.5},
        )
        for kwargs in cases:
            with self.subTest(kwargs=kwargs):
                result = claim_approved_job(
                    self.queue, self.project, approved_paths=("sample.py",),
                    queue_enabled=True, **kwargs,
                )
                self.assertEqual(result["state"], "INVALID_CLAIM_POLICY")
                self.assertFalse(self.queue.exists())

    def test_retry_rejects_nonfinite_policy(self):
        cases = (
            {"now_epoch": float("nan")},
            {"now_epoch": -1},
            {"retry_delay_seconds": float("nan")},
            {"retry_delay_seconds": float("inf")},
            {"retry_delay_seconds": "15"},
            {"max_attempts": True},
        )
        for kwargs in cases:
            with self.subTest(kwargs=kwargs):
                result = report_staging_failure(
                    self.queue, self.job, self.token, reason="TEST_FAILURE",
                    queue_enabled=True, **kwargs,
                )
                self.assertEqual(result["state"], "INVALID_FAILURE_POLICY")
                self.assertFalse(self.queue.exists())

    def test_renewal_rejects_nonfinite_and_invalid_time(self):
        for kwargs in (
            {"now_epoch": float("nan")}, {"now_epoch": "100"},
            {"now_epoch": -1}, {"lease_seconds": float("nan")},
            {"lease_seconds": "20"}, {"lease_seconds": float("inf")},
        ):
            with self.subTest(kwargs=kwargs):
                result = renew_job_lease(
                    self.queue, self.job, self.token, queue_enabled=True, **kwargs,
                )
                self.assertEqual(result["state"], "INVALID_LEASE_POLICY")
                self.assertFalse(self.queue.exists())

    def test_offline_acknowledgement_rejects_nonfinite_clock(self):
        result = acknowledge_staged_bundle(
            self.queue, self.project, self.job, self.token,
            Path(self.temp.name) / "staging" / "build-test",
            now_epoch=float("nan"), queue_enabled=True,
        )
        self.assertEqual(result["state"], "INVALID_LEASE_POLICY")
        self.assertFalse(result["acknowledged"])
        self.assertFalse(self.queue.exists())


if __name__ == "__main__":
    unittest.main()
