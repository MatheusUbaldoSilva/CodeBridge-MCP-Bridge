"""P9-B installed claim ownership, synthetic SQLite and OS lock only."""
from contextlib import closing
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from rag.runtime.incremental_installed_claim_gate import inspect_installed_claim_ownership
from rag.runtime.incremental_job_queue import _connection
from rag.runtime.incremental_supervisor_fence import issue_generation
from rag.runtime.incremental_supervisor_lock import SupervisorLock


class InstalledClaimOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "CodeBridge" / "rag"
        self.jobs = self.root / "jobs"
        self.jobs.mkdir(parents=True)
        self.queue = self.jobs / "incremental_jobs.sqlite3"
        self.fence = self.jobs / "supervisor_fence.sqlite3"
        self.lock_path = self.jobs / "supervisor.lock"
        with closing(_connection(self.queue, create=True)):
            pass
        self.public = {
            "state": "PUBLIC_POINTER_OBSERVED",
            "generation": "v1_delta_1ae1d01ea84f4e",
        }

    def assess(self, lock, generation, **overrides):
        with patch(
            "rag.runtime.incremental_installed_claim_gate.resolve_rag_sqlite_path",
            return_value=self.root / "rag_index.sqlite3",
        ), patch(
            "rag.runtime.incremental_installed_scheduler_preflight.resolve_rag_sqlite_path",
            return_value=self.root / "rag_index.sqlite3",
        ), patch(
            "rag.runtime.incremental_installed_scheduler_preflight.inspect_public_pointer_for_scheduler",
            return_value=self.public,
        ):
            params = {
                "approved_source_paths": ("sample.py",), "queue_enabled": True,
                "worker_enabled": True, "scheduler_enabled": True,
                "recovery_verified": True, "installed_runtime_verified": True,
                "public_integrity_verified": True,
                **overrides,
            }
            return inspect_installed_claim_ownership(
                lock=lock, expected_generation=generation, **params,
            )

    def test_no_lock_cannot_reach_claim_gate(self):
        report = self.assess(None, 1)
        self.assertEqual(report["blockers"], ["INSTALLED_SUPERVISOR_LOCK_NOT_OWNED"])
        self.assertFalse(report["queue_claimed"])

    def test_exact_lock_and_live_fence_are_observation_only(self):
        with SupervisorLock(self.lock_path) as lock:
            gen = issue_generation(self.fence, lock=lock)
            report = self.assess(lock, gen)
            self.assertEqual(report["state"], "CLAIM_PREREQUISITES_OBSERVED_ONLY")
            self.assertTrue(report["lock_owned"])
            self.assertTrue(report["must_recheck_before_claim"])
            self.assertFalse(report["queue_claimed"])
            self.assertFalse(report["activation_authorized"])
        self.assertEqual(self.assess(lock, gen)["state"], "INSTALLED_CLAIM_BLOCKED")

    def test_foreign_lock_in_same_directory_is_not_accepted(self):
        with SupervisorLock(self.jobs / "foreign.lock") as foreign:
            gen = issue_generation(self.fence, lock=foreign)
            report = self.assess(foreign, gen)
            self.assertEqual(report["blockers"], ["INSTALLED_SUPERVISOR_LOCK_NOT_OWNED"])

    def test_stale_generation_under_valid_lock_is_rejected(self):
        with SupervisorLock(self.lock_path) as lock:
            former = issue_generation(self.fence, lock=lock)
            latest = issue_generation(self.fence, lock=lock)
            self.assertEqual(latest, former + 1)
            stale = self.assess(lock, former)
            self.assertEqual(stale["blockers"], ["INSTALLED_SUPERVISOR_GENERATION_STALE"])
            new = self.assess(lock, latest)
            self.assertEqual(new["state"], "CLAIM_PREREQUISITES_OBSERVED_ONLY")

    def test_missing_approval_retains_lock_but_cannot_claim(self):
        with SupervisorLock(self.lock_path) as lock:
            gen = issue_generation(self.fence, lock=lock)
            report = self.assess(lock, gen, approved_source_paths=())
            self.assertEqual(report["state"], "INSTALLED_CLAIM_BLOCKED")
            self.assertIn("SOURCE_APPROVAL_REQUIRED", report["preflight_blockers"])
            self.assertFalse(report["queue_claimed"])


if __name__ == "__main__":
    unittest.main()
