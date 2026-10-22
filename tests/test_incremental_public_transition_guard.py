import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from rag.runtime.incremental_installed_scheduler_preflight import inspect_installed_scheduler_preflight


class PendingPublicTransitionGuardTests(unittest.TestCase):
    def test_pending_public_journal_blocks_scheduler_without_worker(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "production-generation-transition.json").write_text('{"state":"PREPARED"}')
            with patch(
                "rag.runtime.incremental_installed_scheduler_preflight.resolve_rag_sqlite_path",
                return_value=root / "rag_index.sqlite3",
            ), patch(
                "rag.runtime.incremental_installed_scheduler_preflight.assess_autonomous_worker_gate",
                side_effect=AssertionError("scheduler eligibility must not be read"),
            ):
                report = inspect_installed_scheduler_preflight()
            self.assertEqual(report["blockers"], ["PUBLIC_GENERATION_TRANSITION_PENDING"])
            self.assertFalse(report["worker_started"])
            self.assertFalse(report["scheduler_started"])


if __name__ == "__main__":
    unittest.main()
