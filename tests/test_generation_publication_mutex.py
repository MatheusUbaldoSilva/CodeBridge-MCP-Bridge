"""Publication mutex prevents activation/retirement race; no deletion."""
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rag.runtime.generation_activation import activate_test_generation, PUBLICATION_LOCK_NAME
from rag.runtime.generation_process_lock import generation_lock, GenerationBusy
from rag.runtime.generation_protected_session import protected_generation_retirement
from rag.runtime.generation_pointer import resolve_generation
from test_generation_read_session import create_generation


class PublicationMutexTests(unittest.TestCase):
    def test_retirement_blocks_activation_of_that_generation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "codebridge-rag-generation-test"
            root.mkdir()
            create_generation(root, "one")
            create_generation(root, "two")
            activate_test_generation(root, "two")
            with protected_generation_retirement(root, "one"):
                with self.assertRaises(GenerationBusy):
                    activate_test_generation(root, "one")
                self.assertEqual(resolve_generation(root).generation, "two")
            activate_test_generation(root, "one")
            self.assertEqual(resolve_generation(root).generation, "one")

    def test_publication_lock_blocks_activation_and_retirement(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "codebridge-rag-generation-test"
            root.mkdir()
            create_generation(root, "one")
            create_generation(root, "two")
            activate_test_generation(root, "one")
            with generation_lock(root, PUBLICATION_LOCK_NAME, exclusive=True):
                with self.assertRaises(GenerationBusy):
                    activate_test_generation(root, "two")
                with self.assertRaises(GenerationBusy):
                    with protected_generation_retirement(root, "two"):
                        pass
            self.assertEqual(resolve_generation(root).generation, "one")


if __name__ == "__main__":
    unittest.main()
