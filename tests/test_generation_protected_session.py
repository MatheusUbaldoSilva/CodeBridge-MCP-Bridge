import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rag.runtime.generation_activation import activate_test_generation
from rag.runtime.generation_process_lock import GenerationBusy
from rag.runtime.generation_protected_session import protected_generation_read, protected_generation_retirement
from rag.runtime.generation_read_session import GenerationReadError
from test_generation_read_session import create_generation

class ProtectedSessionTests(unittest.TestCase):
    def test_active_read_blocks_retirement_after_switch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "codebridge-rag-generation-test"
            root.mkdir()
            create_generation(root, "one")
            create_generation(root, "two")
            activate_test_generation(root, "one")
            with protected_generation_read(root) as session:
                activate_test_generation(root, "two")
                self.assertEqual(session.name, "one")
                with self.assertRaises(GenerationBusy):
                    with protected_generation_retirement(root, "one"):
                        pass
            with protected_generation_retirement(root, "one") as folder:
                self.assertEqual(folder.name, "one")
            with self.assertRaises(GenerationReadError):
                with protected_generation_retirement(root, "two"):
                    pass
            with protected_generation_read(root) as new_session:
                self.assertEqual(new_session.name, "two")

    def test_no_active_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "codebridge-rag-generation-test"
            root.mkdir()
            with self.assertRaises(GenerationReadError):
                with protected_generation_read(root):
                    pass

if __name__ == "__main__":
    unittest.main()
