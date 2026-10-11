import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_validate import fixture
from rag.runtime.generation_controlled_restore import (
    restore_test_generation, ControlledRestoreError,
)
from rag.runtime.generation_pointer import resolve_generation
from rag.runtime.generation_activation import activate_test_generation
from rag.runtime.generation_recovery_candidate import RecoveryCandidateError


class ControlledRestoreTests(unittest.TestCase):
    def test_explicit_candidate_revalidated_and_activated(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "codebridge-rag-generation-test"
            one = root / "generations" / "one"
            two = root / "generations" / "two"
            one.mkdir(parents=True)
            two.mkdir()
            fixture(one)
            fixture(two)
            activate_test_generation(root, "one")
            result = restore_test_generation(root, "two")
            self.assertEqual(result["state"], "TEST_RESTORED")
            self.assertEqual(result["previous"], "one")
            self.assertEqual(resolve_generation(root).generation, "two")
            self.assertTrue(one.is_dir())

    def test_failed_revalidation_preserves_active(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "codebridge-rag-generation-test"
            one = root / "generations" / "one"
            two = root / "generations" / "two"
            one.mkdir(parents=True)
            two.mkdir()
            fixture(one)
            activate_test_generation(root, "one")
            (two / "rag_index.sqlite3").write_bytes(b"bad")
            with self.assertRaises(RecoveryCandidateError):
                restore_test_generation(root, "two")
            self.assertEqual(resolve_generation(root).generation, "one")

    def test_injected_failure_preserves_active(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "codebridge-rag-generation-test"
            one = root / "generations" / "one"
            two = root / "generations" / "two"
            one.mkdir(parents=True)
            two.mkdir()
            fixture(one)
            fixture(two)
            activate_test_generation(root, "one")
            with self.assertRaises(ControlledRestoreError):
                restore_test_generation(root, "two", fail_before_switch=True)
            self.assertEqual(resolve_generation(root).generation, "one")
            self.assertFalse(list(root.glob(".restore-generation.*.tmp")))


if __name__ == "__main__":
    unittest.main()
