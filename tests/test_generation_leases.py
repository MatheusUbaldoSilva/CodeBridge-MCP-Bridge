import sys
import tempfile
import threading
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rag.runtime.generation_leases import GenerationLeaseRegistry
from rag.runtime.generation_activation import activate_test_generation
from test_generation_read_session import create_generation


class LeaseTests(unittest.TestCase):
    def test_hold_old_generation_during_activation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "codebridge-rag-generation-test"
            root.mkdir()
            create_generation(root, "one")
            create_generation(root, "two")
            activate_test_generation(root, "one")
            registry = GenerationLeaseRegistry()
            with registry.acquire(root) as session:
                activate_test_generation(root, "two")
                self.assertEqual(session.name, "one")
                self.assertFalse(registry.can_retire("one", "two"))
                self.assertTrue(registry.can_retire("unused", "two"))
                self.assertFalse(registry.can_retire("two", "two"))
            self.assertTrue(registry.can_retire("one", "two"))
            self.assertEqual(registry.snapshot(), {})

    def test_concurrent_readers_and_exception_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "codebridge-rag-generation-test"
            root.mkdir()
            create_generation(root, "one")
            activate_test_generation(root, "one")
            registry = GenerationLeaseRegistry()
            entered = threading.Event()
            release = threading.Event()
            def reader():
                with registry.acquire(root):
                    entered.set()
                    release.wait(timeout=5)
            thread = threading.Thread(target=reader)
            thread.start()
            try:
                self.assertTrue(entered.wait(5))
                with registry.acquire(root):
                    self.assertEqual(registry.snapshot(), {"one": 2})
                self.assertEqual(registry.snapshot(), {"one": 1})
            finally:
                release.set()
                thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
            self.assertEqual(registry.snapshot(), {})
            with self.assertRaises(ValueError):
                with registry.acquire(root):
                    raise ValueError("test")
            self.assertEqual(registry.snapshot(), {})


if __name__ == "__main__":
    unittest.main()
