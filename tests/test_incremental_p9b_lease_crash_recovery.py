"""P9-B isolated interrupted-job recovery and lease ownership tests.

All SQLite writes are confined to TemporaryDirectory.
"""
from pathlib import Path
import subprocess
import tempfile
import unittest

from rag.chunking.provenance import source_sha256
from rag.runtime.incremental_supervisor_fence import issue_generation, observe_generation
from rag.runtime.incremental_supervisor_lock import SupervisorLock
from rag.runtime.incremental_job_queue import (
    claim_approved_job, enqueue_source_event, inspect_job,
    inspect_job_queue, renew_job_lease, report_staging_failure,
)


class InterruptedLeaseRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.repo = root / "CodeBridge-MCP-Bridge"
        self.repo.mkdir()
        self.source = self.repo / "sample.py"
        self.source.write_text("def approved():\n    return True\n", encoding="utf-8")
        self.db = root / "jobs" / "incremental_jobs.sqlite3"
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        subprocess.run(["git", "-C", str(self.repo), "add", "sample.py"], check=True)
        subprocess.run(["git", "-C", str(self.repo),
                        "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                        "commit", "-q", "-m", "approved"], check=True)
        self.head = subprocess.check_output(
            ["git", "-C", str(self.repo), "rev-parse", "HEAD"], text=True,
        ).strip()
        self.sha = source_sha256(self.source.read_text(encoding="utf-8"))
        result = enqueue_source_event(
            self.db, self.repo, "sample.py", approved_paths=("sample.py",),
            observed_commit=self.head, observed_sha256=self.sha,
            changed_at_epoch=100, debounce_seconds=30,
            now_epoch=140, queue_enabled=True,
        )
        self.assertEqual(result["state"], "QUEUED_DURABLY")

    def claim(self, now, *, lease=10, max_attempts=3):
        return claim_approved_job(
            self.db, self.repo, approved_paths=("sample.py",),
            now_epoch=now, queue_enabled=True, lease_seconds=lease,
            max_attempts=max_attempts,
        )

    def test_expired_first_worker_cannot_renew_second_workers_lease(self):
        first = self.claim(141)
        self.assertEqual(first["state"], "CLAIMED_FOR_OFFLINE_STAGING")
        self.assertEqual(self.claim(149)["state"], "QUEUE_EMPTY")
        recovered = self.claim(152)
        self.assertEqual(recovered["state"], "CLAIMED_FOR_OFFLINE_STAGING")
        self.assertEqual(recovered["attempts"], 2)
        self.assertNotEqual(first["lease_token"], recovered["lease_token"])
        previous = renew_job_lease(
            self.db, first["job_id"], first["lease_token"],
            now_epoch=153, queue_enabled=True, lease_seconds=20,
        )
        self.assertFalse(previous["renewed"])
        current = renew_job_lease(
            self.db, recovered["job_id"], recovered["lease_token"],
            now_epoch=153, queue_enabled=True, lease_seconds=20,
        )
        self.assertTrue(current["renewed"])
        self.assertFalse(current["active_index_updated"])

    def test_expired_lease_eventually_fails_at_max_attempts(self):
        first = self.claim(141, max_attempts=2)
        self.assertEqual(first["attempts"], 1)
        second = self.claim(152, max_attempts=2)
        self.assertEqual(second["attempts"], 2)
        final = self.claim(163, max_attempts=2)
        self.assertEqual(final["state"], "QUEUE_EMPTY")
        state = inspect_job(self.db, first["job_id"])
        self.assertEqual(state["job_state"], "FAILED")
        self.assertEqual(state["last_error"], "WORKER_LEASE_EXPIRED")
        self.assertEqual(inspect_job_queue(self.db)["by_state"], {"FAILED": 1})

    def test_restart_requires_new_supervisor_generation_and_new_job_lease(self):
        fence = self.db.parent / "supervisor_fence.sqlite3"
        lock_file = self.db.parent / "supervisor.lock"

        with SupervisorLock(lock_file) as supervisor:
            old_generation = issue_generation(fence, lock=supervisor)
            first = self.claim(141)
            self.assertTrue(observe_generation(fence, old_generation))
            self.assertEqual(first["attempts"], 1)

        # A new process can reacquire the OS lock; it must still mint a
        # strictly newer durable generation, invalidating the old instance.
        with SupervisorLock(lock_file) as recovered_supervisor:
            new_generation = issue_generation(fence, lock=recovered_supervisor)
            self.assertEqual(new_generation, old_generation + 1)
            self.assertFalse(observe_generation(fence, old_generation))
            self.assertTrue(observe_generation(fence, new_generation))
            self.assertEqual(self.claim(149)["state"], "QUEUE_EMPTY")
            fresh = self.claim(152)
            self.assertEqual(fresh["attempts"], 2)
            self.assertNotEqual(fresh["lease_token"], first["lease_token"])

            expired_worker = renew_job_lease(
                self.db, first["job_id"], first["lease_token"],
                now_epoch=153, lease_seconds=20, queue_enabled=True,
            )
            self.assertFalse(expired_worker["renewed"])
            self.assertEqual(inspect_job(self.db, first["job_id"])["job_state"], "CLAIMED")
            self.assertTrue(observe_generation(fence, new_generation))

    def test_stale_worker_cannot_erase_recovered_claim(self):
        first = self.claim(141)
        second = self.claim(152)
        stale = report_staging_failure(
            self.db, first["job_id"], first["lease_token"],
            reason="STALE_WORKER", now_epoch=153, queue_enabled=True,
        )
        self.assertFalse(stale.get("acknowledged", False))
        self.assertEqual(inspect_job(self.db, first["job_id"])["job_state"], "CLAIMED")
        active = report_staging_failure(
            self.db, second["job_id"], second["lease_token"],
            reason="SYNTHETIC_RETRY", now_epoch=154, queue_enabled=True,
        )
        self.assertEqual(active["state"], "SCHEDULED_RETRY")
        self.assertEqual(inspect_job(self.db, first["job_id"])["job_state"], "RETRY")


if __name__ == "__main__":
    unittest.main()
