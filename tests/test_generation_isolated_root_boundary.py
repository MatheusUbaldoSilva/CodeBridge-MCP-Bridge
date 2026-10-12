"""Regression: marker in an ancestor cannot authorize test-generation writes."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rag.runtime.generation_activation import (
    activate_test_generation, GenerationActivationError)
from rag.runtime.generation_controlled_restore import (
    restore_test_generation, ControlledRestoreError)
from rag.runtime.generation_process_lock import generation_lock
from rag.runtime.generation_recovery import inspect_test_generation_recovery
from rag.runtime.generation_recovery_candidate import (
    verify_recovery_candidate, inspect_recovery_candidates, RecoveryCandidateError)
from rag.runtime.generation_test_authorization import TestPublicationAuthorization
from rag.runtime.generation_transition_journal import (
    prepare_transition, inspect_pending_transition, TransitionRecoveryError)
from rag.runtime.generation_verified_backup import (
    backup_generation, verify_generation_backup, VerifiedBackupError)


class TestRootBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.marker = Path(self.temp.name) / "codebridge-rag-generation-test"
        self.fake_production = self.marker / "not-the-test-root"
        self.fake_production.mkdir(parents=True)

    def test_rejects_marker_in_ancestor_for_all_mutating_entry_points(self):
        root = self.fake_production
        cases = [
            (lambda: activate_test_generation(root, "one"), GenerationActivationError),
            (lambda: restore_test_generation(root, "one"), ControlledRestoreError),
            (lambda: backup_generation(root, "one", "before"), VerifiedBackupError),
            (lambda: verify_generation_backup(root, "before"), VerifiedBackupError),
            (lambda: prepare_transition(root, "one", "two"), TransitionRecoveryError),
            (lambda: TestPublicationAuthorization(
                root, "one", "two", "demo", root, {}, {}), ValueError),
        ]
        for call, error in cases:
            with self.subTest(operation=call):
                with self.assertRaises(error):
                    call()
        self.assertFalse((root / "locks").exists())
        self.assertFalse((root / "backups").exists())
        self.assertFalse((root / "transition-pending.json").exists())
        self.assertFalse((root / "active-generation.json").exists())

    def test_rejects_marker_in_ancestor_for_reads_and_lock(self):
        root = self.fake_production
        cases = [
            (lambda: inspect_test_generation_recovery(root), ValueError),
            (lambda: inspect_recovery_candidates(root), RecoveryCandidateError),
            (lambda: verify_recovery_candidate(root, "one"), RecoveryCandidateError),
            (lambda: inspect_pending_transition(root), TransitionRecoveryError),
        ]
        for call, error in cases:
            with self.subTest(operation=call):
                with self.assertRaises(error):
                    call()
        with self.assertRaises(ValueError):
            with generation_lock(root, "one"):
                pass
        self.assertFalse((root / "locks").exists())


if __name__ == "__main__":
    unittest.main()
