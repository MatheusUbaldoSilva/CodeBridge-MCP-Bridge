"""Synthetic quiescence sampling never grants real copy authorization."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
from rag.runtime.offline_quiescence_window import inspect_synthetic_quiet_window


def clean():
    return {"process_listing_ok": True, "state": "UNPROVEN_QUIESCENCE"}


class QuiescenceWindowTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / "codebridge-rag-generation-test"
        create_bundle(self.root, [("alpha", "note", "synthetic")])

    def test_stable_fixture_never_authorizes_copy(self):
        result = inspect_synthetic_quiet_window(self.root, process_inspector=clean,
                                                pause=lambda seconds: None)
        self.assertEqual(result["state"], "LAB_STABLE_BUT_UNPROVEN")
        self.assertEqual(result["samples_completed"], 3)
        self.assertFalse(result["copy_authorized"])
        self.assertFalse(result["production_quiescence_proven"])

    def test_external_cli_always_blocks_and_needs_explicit_lab_flag(self):
        import json
        import subprocess
        cli = Path(__file__).resolve().parents[1] / "rag_offline_quiescence_window_cli.py"
        command = [sys.executable, str(cli), "--fixture-root", str(self.root)]
        missing_flag = subprocess.run(command, capture_output=True, text=True, timeout=15)
        self.assertNotEqual(missing_flag.returncode, 0)
        completed = subprocess.run(command + ["--lab-only"],
                                   capture_output=True, text=True, timeout=15)
        self.assertEqual(completed.returncode, 2)
        result = json.loads(completed.stdout)
        self.assertEqual(result["state"], "BLOCKED")
        self.assertFalse(result["copy_authorized"])

    def test_active_process_blocks(self):
        result = inspect_synthetic_quiet_window(
            self.root, process_inspector=lambda: {"process_listing_ok": True, "state": "BLOCKED"},
            pause=lambda seconds: None)
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("ACTIVE_OR_UNVERIFIED_PROCESSES", result["issues"])

    def test_process_listing_failure_blocks(self):
        result = inspect_synthetic_quiet_window(
            self.root, process_inspector=lambda: {"process_listing_ok": False},
            pause=lambda seconds: None)
        self.assertEqual(result["state"], "BLOCKED")

    def test_mutated_fixture_during_window_blocks(self):
        calls = []
        def mutate(seconds):
            calls.append(seconds)
            (self.root / "rag-index-manifest.json").write_bytes(b"tampered")
        result = inspect_synthetic_quiet_window(self.root, process_inspector=clean,
                                                pause=mutate)
        self.assertEqual(result["state"], "BLOCKED")
        self.assertTrue(any(x in result["issues"] for x in ("FIXTURE_CHANGED_DURING_WINDOW", "PermissionError")))

    def test_invalid_root_and_samples_block(self):
        self.assertEqual(inspect_synthetic_quiet_window(self.root.parent,
            process_inspector=clean)["state"], "BLOCKED")
        self.assertEqual(inspect_synthetic_quiet_window(self.root, samples=1,
            process_inspector=clean)["state"], "BLOCKED")

    def test_failed_inspector_blocks_without_throwing(self):
        def broken():
            raise RuntimeError("inventory unavailable")
        result = inspect_synthetic_quiet_window(self.root, process_inspector=broken)
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("RuntimeError", result["issues"])
        self.assertFalse(result["copy_authorized"])

    def test_conflicting_generation_lock_blocks(self):
        from rag.runtime.generation_process_lock import generation_lock
        with generation_lock(self.root, "offline_capture", exclusive=True):
            result = inspect_synthetic_quiet_window(self.root, process_inspector=clean)
        self.assertEqual(result["state"], "BLOCKED")
        self.assertFalse(result["copy_authorized"])


if __name__ == "__main__":
    unittest.main()
