import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_generation_read_session import create_generation
from rag.runtime.generation_activation import activate_test_generation
from rag.runtime.generation_process_lock import GenerationBusy
from rag.runtime.generation_protected_session import protected_generation_retirement
from rag.runtime.generation_search_paths import (
    isolated_generation_search_paths, GenerationSearchUnavailable,
)
from rag.runtime.generation_transition_journal import JOURNAL, TransitionRecoveryError


class SearchPathsTests(unittest.TestCase):
    def test_pinned_storage_paths_survive_activation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "codebridge-rag-generation-test"
            root.mkdir()
            create_generation(root, "one")
            create_generation(root, "two")
            activate_test_generation(root, "one")
            with isolated_generation_search_paths(root) as selected:
                self.assertEqual(selected.generation, "one")
                self.assertEqual(selected.sqlite.parent, selected.qdrant.parent)
                self.assertEqual(selected.manifest.parent, selected.qdrant.parent)
                activate_test_generation(root, "two")
                with self.assertRaises(GenerationBusy):
                    with protected_generation_retirement(root, "one"):
                        pass
            with isolated_generation_search_paths(root) as selected:
                self.assertEqual(selected.generation, "two")

    def test_pending_transition_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "codebridge-rag-generation-test"
            root.mkdir()
            create_generation(root, "one")
            activate_test_generation(root, "one")
            (root / JOURNAL).write_text("bad")
            with self.assertRaises(GenerationSearchUnavailable):
                with isolated_generation_search_paths(root):
                    pass

    def test_refuses_production_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(TransitionRecoveryError):
                with isolated_generation_search_paths(tmp):
                    pass


if __name__ == "__main__":
    unittest.main()
