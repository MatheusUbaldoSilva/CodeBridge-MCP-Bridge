import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rag.runtime.incremental_installed_scheduler_preflight import inspect_installed_scheduler_preflight


class PointerSnapshotStabilityTests(unittest.TestCase):
    def test_pointer_switch_during_read_only_preflight_blocks(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch(
                "rag.runtime.incremental_installed_scheduler_preflight.resolve_rag_sqlite_path",
                return_value=root / "rag_index.sqlite3",
            ), patch(
                "rag.runtime.incremental_installed_scheduler_preflight.inspect_public_pointer_for_scheduler",
                side_effect=[
                    {"state": "PUBLIC_LEGACY_POINTER", "generation": "legacy"},
                    {"state": "PUBLIC_POINTER_OBSERVED", "generation": "v1_delta_1ae1d01ea84f4e"},
                ],
            ), patch(
                "rag.runtime.incremental_installed_scheduler_preflight.assess_autonomous_worker_gate",
                return_value={"state": "PREREQUISITES_OBSERVED_ONLY", "blockers": [],
                              "scheduler_started": False, "worker_started": False,
                              "active_index_updated": False, "safe_to_publish": False,
                              "activation_authorized": False},
            ):
                report = inspect_installed_scheduler_preflight(
                    queue_db=root / "jobs" / "incremental_jobs.sqlite3",
                    durable_store=root / "jobs" / "supervisor_fence.sqlite3",
                    expected_durable_generation=1,
                )
        self.assertEqual(report["state"], "AUTONOMOUS_SCHEDULING_BLOCKED")
        self.assertIn("PUBLIC_POINTER_CHANGED_DURING_PREFLIGHT", report["blockers"])
        self.assertFalse(report["scheduler_started"])
        self.assertFalse(report["activation_authorized"])


if __name__ == "__main__":
    unittest.main()
