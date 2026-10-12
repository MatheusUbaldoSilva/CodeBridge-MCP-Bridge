"""Two publishers competing for the same generation must never both commit."""
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_validate import fixture
from rag.runtime.generation_activation import activate_test_generation
from rag.runtime.generation_pointer import resolve_generation
from rag.runtime.generation_backup_publish import publish_with_verified_backup
from rag.runtime.generation_transition_journal import inspect_pending_transition


class ConcurrentBackupPublishTests(unittest.TestCase):
    def test_competing_publishers_only_one_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"codebridge-rag-generation-test"
            for name in ("one","two","three"):
                folder=root/"generations"/name
                folder.mkdir(parents=True)
                fixture(folder)
            activate_test_generation(root,"one")
            entered=threading.Event()
            release=threading.Event()
            outcomes=[]
            import rag.runtime.generation_backup_publish as module
            original=module.backup_generation

            def delayed(root_arg,previous,backup_name):
                if backup_name=="first":
                    entered.set()
                    if not release.wait(8):
                        raise TimeoutError("backup test not released")
                return original(root_arg,previous,backup_name)

            def first():
                try:
                    outcomes.append(("first",publish_with_verified_backup(root,"one","two","first")))
                except Exception as exc:
                    outcomes.append(("first",type(exc).__name__))

            with patch.object(module,"backup_generation",side_effect=delayed):
                worker=threading.Thread(target=first,daemon=True)
                worker.start()
                try:
                    self.assertTrue(entered.wait(4))
                    try:
                        second=publish_with_verified_backup(root,"one","three","second")
                        outcomes.append(("second",second))
                    except Exception as exc:
                        outcomes.append(("second",type(exc).__name__))
                finally:
                    release.set()
                    worker.join(12)
            self.assertFalse(worker.is_alive())
            successes=[name for name,result in outcomes if isinstance(result,dict)]
            self.assertEqual(len(successes),1,outcomes)
            self.assertIn(resolve_generation(root).generation,("two","three"))
            self.assertEqual(inspect_pending_transition(root)["state"],"NO_PENDING_TRANSITION")


if __name__=="__main__":
    unittest.main()
