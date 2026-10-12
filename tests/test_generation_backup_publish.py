import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_validate import fixture
from rag.runtime.generation_activation import activate_test_generation
from rag.runtime.generation_pointer import resolve_generation
from rag.runtime.generation_backup_publish import publish_with_verified_backup
from rag.runtime.generation_verified_backup import verify_generation_backup
from rag.runtime.generation_transition_journal import (
    recover_pending_transition, inspect_pending_transition, TransitionRecoveryError)


class BackupGatedPublicationTests(unittest.TestCase):
    def setup_root(self, temp):
        root=Path(temp)/"codebridge-rag-generation-test"
        for name in ("one","two"):
            folder=root/"generations"/name
            folder.mkdir(parents=True)
            fixture(folder)
        activate_test_generation(root,"one")
        return root

    def test_backup_exists_and_is_valid_after_success(self):
        with tempfile.TemporaryDirectory() as temp:
            root=self.setup_root(temp)
            result=publish_with_verified_backup(root,"one","two","before_change")
            self.assertEqual(result["state"],"BACKUP_GATED_TEST_PUBLICATION")
            self.assertEqual(resolve_generation(root).generation,"two")
            self.assertEqual(verify_generation_backup(root,"before_change")["documents"],1)

    def test_failure_after_backup_does_not_change_active(self):
        with tempfile.TemporaryDirectory() as temp:
            root=self.setup_root(temp)
            with self.assertRaisesRegex(RuntimeError,"injected interruption"):
                publish_with_verified_backup(root,"one","two","before_change",fail_after_backup=True)
            self.assertEqual(resolve_generation(root).generation,"one")
            self.assertEqual(inspect_pending_transition(root)["state"],"NO_PENDING_TRANSITION")
            self.assertEqual(verify_generation_backup(root,"before_change")["documents"],1)

    def test_failure_after_switch_retains_verified_backup_for_recovery(self):
        with tempfile.TemporaryDirectory() as temp:
            root=self.setup_root(temp)
            with self.assertRaises(TransitionRecoveryError):
                publish_with_verified_backup(root,"one","two","before_change",fail_after_switch=True)
            self.assertEqual(verify_generation_backup(root,"before_change")["documents"],1)
            self.assertEqual(recover_pending_transition(root)["generation"],"one")
            self.assertEqual(resolve_generation(root).generation,"one")


if __name__=="__main__":
    unittest.main()
