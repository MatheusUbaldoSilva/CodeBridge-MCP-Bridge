"""P9-B synthetic installed supervisor prerequisites, without a production queue."""
from contextlib import closing
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from rag.runtime.incremental_job_queue import _connection
from rag.runtime.incremental_supervisor_fence import issue_generation
from rag.runtime.incremental_supervisor_lock import SupervisorLock
from rag.runtime.incremental_installed_scheduler_preflight import inspect_installed_scheduler_preflight


class InstalledSupervisorReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "CodeBridge" / "rag"
        self.jobs = self.root / "jobs"
        self.jobs.mkdir(parents=True)
        self.queue = self.jobs / "incremental_jobs.sqlite3"
        self.fence = self.jobs / "supervisor_fence.sqlite3"
        self.lock = self.jobs / "supervisor.lock"
        with closing(_connection(self.queue, create=True)):
            pass
        with SupervisorLock(self.lock) as held:
            self.generation = issue_generation(self.fence, lock=held)

    def assess(self, generation):
        pointer = {"state": "PUBLIC_POINTER_OBSERVED",
                   "generation": "v1_delta_1ae1d01ea84f4e"}
        with patch(
            "rag.runtime.incremental_installed_scheduler_preflight.resolve_rag_sqlite_path",
            return_value=self.root / "rag_index.sqlite3",
        ), patch(
            "rag.runtime.incremental_installed_scheduler_preflight.inspect_public_pointer_for_scheduler",
            return_value=pointer,
        ):
            return inspect_installed_scheduler_preflight(
                queue_db=self.queue, durable_store=self.fence,
                expected_durable_generation=generation,
                approved_source_paths=("rag/runtime/sample.py",),
                queue_enabled=True, worker_enabled=True, scheduler_enabled=True,
                recovery_verified=True, installed_runtime_verified=True,
                public_integrity_verified=True,
            )

    def test_all_prerequisites_are_observations_not_activation(self):
        report = self.assess(self.generation)
        self.assertEqual(report["state"], "PREREQUISITES_OBSERVED_ONLY")
        self.assertEqual(report["blockers"], [])
        self.assertFalse(report["scheduler_started"])
        self.assertFalse(report["worker_started"])
        self.assertFalse(report["activation_authorized"])
        self.assertFalse(report["safe_to_publish"])

    def test_old_generation_fails_after_fence_rotates(self):
        with SupervisorLock(self.lock) as held:
            new_generation = issue_generation(self.fence, lock=held)
        self.assertEqual(new_generation, self.generation + 1)
        old = self.assess(self.generation)
        self.assertEqual(old["state"], "AUTONOMOUS_SCHEDULING_BLOCKED")
        self.assertIn("DURABLE_FENCE_UNVERIFIED", old["blockers"])
        new = self.assess(new_generation)
        self.assertEqual(new["state"], "PREREQUISITES_OBSERVED_ONLY")

    def test_schema_is_inspected_and_rejected_if_corrupt(self):
        from sqlite3 import connect
        with closing(connect(self.queue)) as db:
            db.execute("PRAGMA user_version=13")
            db.commit()
        result = self.assess(self.generation)
        self.assertEqual(result["state"], "AUTONOMOUS_SCHEDULING_BLOCKED")
        self.assertIn("QUEUE_STORE_INVALID", result["blockers"])

    def test_pending_transition_preempts_durable_ready_state(self):
        (self.root / "production-generation-transition.json").write_text("{}")
        result = self.assess(self.generation)
        self.assertEqual(result["blockers"], ["PUBLIC_GENERATION_TRANSITION_PENDING"])
        self.assertFalse(result["safe_to_publish"])


if __name__ == "__main__":
    unittest.main()
