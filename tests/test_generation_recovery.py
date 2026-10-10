import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rag.runtime.generation_activation import activate_test_generation
from rag.runtime.generation_recovery import inspect_test_generation_recovery
from test_generation_read_session import create_generation


class GenerationRecoveryTests(unittest.TestCase):
    def test_active_and_stale_temporary_pointer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "codebridge-rag-generation-test"
            root.mkdir()
            create_generation(root, "one")
            activate_test_generation(root, "one")
            (root / ".active-generation.crashed.tmp").write_text("partial")
            report = inspect_test_generation_recovery(root)
            self.assertEqual(report["state"], "ACTIVE_GENERATION_AVAILABLE")
            self.assertEqual(report["active"], "one")
            self.assertEqual(report["temporary_pointer_files"], [".active-generation.crashed.tmp"])
            self.assertTrue((root / ".active-generation.crashed.tmp").exists())

    def test_corrupt_pointer_blocked_without_guessing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "codebridge-rag-generation-test"
            root.mkdir()
            create_generation(root, "one")
            (root / "active-generation.json").write_text("{partial")
            report = inspect_test_generation_recovery(root)
            self.assertEqual(report["state"], "BLOCKED_MANUAL_RECOVERY")
            self.assertIsNone(report["active"])

    def test_incomplete_generation_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "codebridge-rag-generation-test"
            root.mkdir()
            create_generation(root, "one")
            activate_test_generation(root, "one")
            (root/"generations"/"one"/"rag_index.sqlite3").unlink()
            report = inspect_test_generation_recovery(root)
            self.assertEqual(report["state"], "BLOCKED_MANUAL_RECOVERY")

    def test_no_pointer_is_not_automatically_recovered(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "codebridge-rag-generation-test"
            root.mkdir()
            create_generation(root, "one")
            report = inspect_test_generation_recovery(root)
            self.assertEqual(report["state"], "LEGACY_OR_NOT_ACTIVATED")


if __name__ == "__main__":
    unittest.main()
