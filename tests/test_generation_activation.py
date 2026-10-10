import tempfile
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rag.runtime.generation_activation import activate_test_generation, GenerationActivationError
from rag.runtime.generation_pointer import resolve_generation


def generation(root, name):
    directory = root / "generations" / name
    (directory / "qdrant").mkdir(parents=True)
    (directory / "rag_index.sqlite3").write_bytes(b"fixture")
    (directory / "rag-index-manifest.json").write_text("{}")


class ActivationTests(unittest.TestCase):
    def test_switch_and_interruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "codebridge-rag-generation-test"
            root.mkdir()
            generation(root, "one")
            generation(root, "two")
            activate_test_generation(root, "one")
            with self.assertRaises(GenerationActivationError):
                activate_test_generation(root, "two", fail_before_replace=True)
            self.assertEqual(resolve_generation(root).generation, "one")
            self.assertFalse(list(root.glob("*.tmp")))
            activate_test_generation(root, "two")
            self.assertEqual(resolve_generation(root).generation, "two")

    def test_reject_bad_generation_and_non_test_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "codebridge-rag-generation-test"
            root.mkdir()
            with self.assertRaises(GenerationActivationError):
                activate_test_generation(root, "../bad")
            with self.assertRaises(GenerationActivationError):
                activate_test_generation(root, "not-installed")
            with self.assertRaises(GenerationActivationError):
                activate_test_generation(Path(tmp), "one")


if __name__ == "__main__":
    unittest.main()
