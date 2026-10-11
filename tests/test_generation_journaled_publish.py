import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_validate import fixture
from rag.runtime.generation_activation import activate_test_generation
from rag.runtime.generation_pointer import resolve_generation
from rag.runtime.generation_journaled_publish import publish_test_generation
from rag.runtime.generation_transition_journal import (
    inspect_pending_transition, recover_pending_transition, TransitionRecoveryError,
)


class JournaledPublicationTests(unittest.TestCase):
    def make_root(self, folder):
        root = Path(folder) / "codebridge-rag-generation-test"
        for name in ("one", "two"):
            path = root / "generations" / name
            path.mkdir(parents=True)
            fixture(path)
        activate_test_generation(root, "one")
        return root

    def test_success_commits_and_clears_journal(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self.make_root(folder)
            result = publish_test_generation(root, "one", "two")
            self.assertEqual(result["active"], "two")
            self.assertEqual(resolve_generation(root).generation, "two")
            self.assertEqual(inspect_pending_transition(root)["state"], "NO_PENDING_TRANSITION")

    def test_failure_before_switch_requires_recovery(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self.make_root(folder)
            with self.assertRaises(TransitionRecoveryError):
                publish_test_generation(root, "one", "two", fail_before_switch=True)
            self.assertEqual(resolve_generation(root).generation, "one")
            with self.assertRaises(TransitionRecoveryError):
                publish_test_generation(root, "one", "two")
            recover_pending_transition(root)
            self.assertEqual(inspect_pending_transition(root)["state"], "NO_PENDING_TRANSITION")

    def test_failure_after_switch_recovers_previous(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self.make_root(folder)
            with self.assertRaises(TransitionRecoveryError):
                publish_test_generation(root, "one", "two", fail_after_switch=True)
            self.assertEqual(resolve_generation(root).generation, "two")
            with self.assertRaises(TransitionRecoveryError):
                publish_test_generation(root, "two", "one")
            with self.assertRaisesRegex(Exception, "pending transition"):
                activate_test_generation(root, "one")
            self.assertEqual(recover_pending_transition(root)["generation"], "one")
            self.assertEqual(resolve_generation(root).generation, "one")


if __name__ == "__main__":
    unittest.main()
