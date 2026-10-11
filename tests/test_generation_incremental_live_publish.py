"""Offline incremental stage + journal publication while a previous reader is pinned."""
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
from rag.runtime.incremental_bundle_stage import stage_incremental_bundle
from rag.runtime.incremental_bundle_validate import validate_incremental_bundle
from rag.runtime.generation_activation import activate_test_generation
from rag.runtime.generation_journaled_publish import publish_test_generation
from rag.runtime.generation_search_paths import isolated_generation_search_paths
from rag.runtime.generation_protected_session import protected_generation_retirement
from rag.runtime.generation_process_lock import GenerationBusy
from rag.runtime.generation_transition_journal import recover_pending_transition, inspect_pending_transition, TransitionRecoveryError


def documents(paths):
    database=sqlite3.connect(paths.sqlite.resolve().as_uri()+"?mode=ro",uri=True)
    try:
        return set(database.execute("SELECT project_id,content FROM rag_documents").fetchall())
    finally:
        database.close()


class IncrementalLivePublishTests(unittest.TestCase):
    def prepare(self, temp):
        root=Path(temp)/"codebridge-rag-generation-test"
        old=root/"generations"/"one"
        incoming=root/"incoming"
        new=root/"generations"/"two"
        old.parent.mkdir(parents=True)
        create_bundle(old,[("a","first","original"),("b","other","preserved")])
        create_bundle(incoming,[("a","first","revised"),("a","second","new")])
        staged=stage_incremental_bundle(old,incoming,new,"a")
        self.assertEqual(staged["verification"]["documents"],3)
        self.assertEqual(validate_incremental_bundle(new)["vectors"],3)
        activate_test_generation(root,"one")
        return root

    def test_live_reader_stays_old_new_reads_updated(self):
        with tempfile.TemporaryDirectory() as temp:
            root=self.prepare(temp)
            with isolated_generation_search_paths(root) as original:
                self.assertEqual(original.generation,"one")
                before=documents(original)
                self.assertEqual(before,{("a","original"),("b","preserved")})
                publication=publish_test_generation(root,"one","two")
                self.assertEqual(publication["state"],"PUBLISHED_TEST_ONLY")
                self.assertEqual(documents(original),before)
                with self.assertRaises(GenerationBusy):
                    with protected_generation_retirement(root,"one"):
                        pass
                with isolated_generation_search_paths(root) as updated:
                    self.assertEqual(updated.generation,"two")
                    self.assertEqual(documents(updated),{("a","revised"),("a","new"),("b","preserved")})
            with protected_generation_retirement(root,"one") as folder:
                self.assertTrue(folder.is_dir())

    def test_post_switch_failure_recovers_previous_without_deleting_candidate(self):
        with tempfile.TemporaryDirectory() as temp:
            root=self.prepare(temp)
            with self.assertRaises(TransitionRecoveryError):
                publish_test_generation(root,"one","two",fail_after_switch=True)
            self.assertEqual(inspect_pending_transition(root)["state"],"PENDING_TRANSITION")
            self.assertEqual(recover_pending_transition(root)["generation"],"one")
            with isolated_generation_search_paths(root) as paths:
                self.assertEqual(documents(paths),{("a","original"),("b","preserved")})
            self.assertTrue((root/"generations"/"two").is_dir())

if __name__=="__main__":
    unittest.main()
