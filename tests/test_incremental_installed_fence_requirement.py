import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rag.runtime.incremental_installed_scheduler_preflight import inspect_installed_scheduler_preflight


class InstalledDurableFenceRequirementTests(unittest.TestCase):
    def evaluate(self, temp, store, generation):
        root = Path(temp)
        with patch(
            "rag.runtime.incremental_installed_scheduler_preflight.resolve_rag_sqlite_path",
            return_value=root / "rag_index.sqlite3",
        ), patch(
            "rag.runtime.incremental_installed_scheduler_preflight.assess_autonomous_worker_gate",
            side_effect=AssertionError("must not accept unverified installed fence"),
        ):
            return inspect_installed_scheduler_preflight(
                queue_db=root / "jobs" / "incremental_jobs.sqlite3",
                durable_store=store,
                expected_durable_generation=generation,
            )

    def test_fence_not_supplied_denies(self):
        with tempfile.TemporaryDirectory() as temp:
            result = self.evaluate(temp, None, None)
        self.assertIn("INSTALLED_DURABLE_FENCE_REQUIRED", result["blockers"])

    def test_external_fence_denies(self):
        with tempfile.TemporaryDirectory() as temp:
            result = self.evaluate(temp, Path(temp) / "wrong.sqlite3", 1)
        self.assertIn("INSTALLED_DURABLE_FENCE_REQUIRED", result["blockers"])

    def test_bool_generation_denies(self):
        with tempfile.TemporaryDirectory() as temp:
            result = self.evaluate(temp, Path(temp) / "jobs" / "supervisor_fence.sqlite3", True)
        self.assertIn("INSTALLED_DURABLE_FENCE_REQUIRED", result["blockers"])


if __name__ == "__main__":
    unittest.main()
