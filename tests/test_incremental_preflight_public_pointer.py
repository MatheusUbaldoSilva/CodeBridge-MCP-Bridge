import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rag.runtime.incremental_installed_scheduler_preflight import inspect_installed_scheduler_preflight


class PublicPointerPreflightTests(unittest.TestCase):
    def test_invalid_public_pointer_blocks_before_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch(
                "rag.runtime.incremental_installed_scheduler_preflight.resolve_rag_sqlite_path",
                return_value=root / "rag_index.sqlite3",
            ), patch(
                "rag.runtime.incremental_installed_scheduler_preflight.inspect_public_pointer_for_scheduler",
                return_value={"state": "PUBLIC_POINTER_INVALID", "generation": None},
            ), patch(
                "rag.runtime.incremental_installed_scheduler_preflight.assess_autonomous_worker_gate",
                side_effect=AssertionError("gate must not run against invalid pointer"),
            ):
                result = inspect_installed_scheduler_preflight()
        self.assertEqual(result["blockers"], ["PUBLIC_POINTER_UNVERIFIED"])
        self.assertFalse(result["scheduler_started"])
        self.assertFalse(result["active_index_updated"])

    def test_legacy_pointer_remains_diagnostic_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch(
                "rag.runtime.incremental_installed_scheduler_preflight.resolve_rag_sqlite_path",
                return_value=root / "rag_index.sqlite3",
            ), patch(
                "rag.runtime.incremental_installed_scheduler_preflight.inspect_public_pointer_for_scheduler",
                return_value={"state": "PUBLIC_LEGACY_POINTER", "generation": "legacy"},
            ), patch(
                "rag.runtime.incremental_installed_scheduler_preflight.assess_autonomous_worker_gate",
                return_value={"state": "AUTONOMOUS_SCHEDULING_BLOCKED", "blockers": ["QUEUE_STORE_ABSENT"], "scheduler_started": False,
                              "worker_started": False, "active_index_updated": False, "safe_to_publish": False, "activation_authorized": False},
            ):
                result = inspect_installed_scheduler_preflight()
        self.assertEqual(result["state"], "AUTONOMOUS_SCHEDULING_BLOCKED")
        self.assertFalse(result["activation_authorized"])


if __name__ == "__main__":
    unittest.main()
