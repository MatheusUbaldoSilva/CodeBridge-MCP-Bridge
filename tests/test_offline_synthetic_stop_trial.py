"""Test independent synthetic child graceful shutdown while real CodeBridge stays alive."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
from rag.runtime.offline_fixture_snapshot import OfflineFixtureError
from rag.runtime.offline_synthetic_stop_trial import (
    run_synthetic_stop_trial, SyntheticStopTrialError,
)


class SyntheticStopTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / "codebridge-rag-generation-test"
        create_bundle(self.root, [("alpha", "note", "only synthetic")])

    def test_child_handle_blocks_then_gracefully_releases(self):
        result = run_synthetic_stop_trial(self.root)
        self.assertEqual(result["state"], "LAB_CHILD_GRACEFULLY_STOPPED")
        self.assertTrue(result["writer_was_blocked"])
        self.assertTrue(result["handle_released"])
        self.assertEqual(result["child_exit_code"], 0)
        self.assertFalse(result["copy_authorized"])
        self.assertFalse(result["production_quiescence_proven"])

    def test_non_fixture_path_is_rejected(self):
        with self.assertRaises(OfflineFixtureError):
            run_synthetic_stop_trial(self.root.parent)

    def test_missing_database_is_rejected(self):
        (self.root / "rag_index.sqlite3").unlink()
        with self.assertRaises(SyntheticStopTrialError):
            run_synthetic_stop_trial(self.root)

    def test_invalid_timeout_is_rejected(self):
        with self.assertRaises(SyntheticStopTrialError):
            run_synthetic_stop_trial(self.root, timeout=0)


if __name__ == "__main__":
    unittest.main()
