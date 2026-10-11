"""Crash after pointer swap and startup recovery, test-only."""
import multiprocessing as mp
import os
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_validate import fixture
from rag.runtime.generation_activation import activate_test_generation
from rag.runtime.generation_pointer import resolve_generation
from rag.runtime.generation_transition_journal import (
    _atomic_json, prepare_transition, recover_pending_transition,
    inspect_pending_transition, TransitionRecoveryError, JOURNAL,
)


def crash_after_pointer_swap(root):
    _atomic_json(Path(root) / "active-generation.json", {
        "schema_version": 1, "generation": "two",
    })
    os._exit(41)


class TransitionJournalTests(unittest.TestCase):
    def setup_generations(self, root):
        for name in ("one", "two"):
            folder = root / "generations" / name
            folder.mkdir(parents=True)
            fixture(folder)
        activate_test_generation(root, "one")

    def test_crash_after_pointer_swap_recovers_previous(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "codebridge-rag-generation-test"
            root.mkdir()
            self.setup_generations(root)
            prepare_transition(root, "one", "two")
            ctx = mp.get_context("spawn")
            worker = ctx.Process(target=crash_after_pointer_swap, args=(root,))
            worker.start()
            worker.join(timeout=8)
            if worker.is_alive():
                worker.terminate()
                worker.join()
                self.fail("worker did not exit")
            self.assertEqual(worker.exitcode, 41)
            self.assertEqual(resolve_generation(root).generation, "two")
            self.assertEqual(inspect_pending_transition(root)["state"], "PENDING_TRANSITION")
            result = recover_pending_transition(root)
            self.assertEqual(result["state"], "RECOVERED_PREVIOUS")
            self.assertEqual(resolve_generation(root).generation, "one")
            self.assertFalse((root / JOURNAL).exists())
            self.assertTrue((root / "generations" / "two").exists())

    def test_crash_before_pointer_swap_retains_previous(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "codebridge-rag-generation-test"
            root.mkdir()
            self.setup_generations(root)
            prepare_transition(root, "one", "two")
            self.assertEqual(recover_pending_transition(root)["generation"], "one")
            self.assertEqual(resolve_generation(root).generation, "one")

    def test_corrupt_journal_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "codebridge-rag-generation-test"
            root.mkdir()
            self.setup_generations(root)
            (root / JOURNAL).write_text("{garbage")
            with self.assertRaises(TransitionRecoveryError):
                recover_pending_transition(root)
            self.assertEqual(resolve_generation(root).generation, "one")


if __name__ == "__main__":
    unittest.main()
