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
        self.assertEqual(result["stores_verified"], 3)
        self.assertFalse(result["copy_authorized"])
        self.assertFalse(result["production_quiescence_proven"])

    def test_external_cli_does_not_authorize_real_backup(self):
        import json
        import subprocess
        cli = Path(__file__).resolve().parents[1] / "rag_offline_synthetic_stop_cli.py"
        base = [sys.executable, str(cli), "--fixture-root", str(self.root)]
        denied = subprocess.run(base, capture_output=True, text=True, timeout=15)
        self.assertNotEqual(denied.returncode, 0)
        result = subprocess.run(base + ["--lab-only"], capture_output=True,
                                text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["stores_verified"], 3)
        self.assertFalse(report["copy_authorized"])
        self.assertFalse(report["production_quiescence_proven"])

    def test_non_fixture_path_is_rejected(self):
        with self.assertRaises(OfflineFixtureError):
            run_synthetic_stop_trial(self.root.parent)

    def test_missing_database_is_rejected(self):
        (self.root / "rag_index.sqlite3").unlink()
        with self.assertRaises(SyntheticStopTrialError):
            run_synthetic_stop_trial(self.root)

    def test_missing_manifest_rejected_before_spawning_child(self):
        (self.root / "rag-index-manifest.json").unlink()
        with self.assertRaises(SyntheticStopTrialError):
            run_synthetic_stop_trial(self.root)

    def test_missing_qdrant_rejected_before_spawning_child(self):
        import shutil
        shutil.rmtree(self.root / "qdrant")
        with self.assertRaises(SyntheticStopTrialError):
            run_synthetic_stop_trial(self.root)

    def test_invalid_timeout_is_rejected(self):
        with self.assertRaises(SyntheticStopTrialError):
            run_synthetic_stop_trial(self.root, timeout=0)


if __name__ == "__main__":
    unittest.main()
