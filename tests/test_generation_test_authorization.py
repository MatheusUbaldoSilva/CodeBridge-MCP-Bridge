import tempfile
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
from rag.runtime.generation_activation import activate_test_generation
from rag.runtime.generation_pointer import resolve_generation
from rag.runtime.incremental_preview_confirmation import snapshot_preview
from rag.runtime.incremental_review_contract import build_review_contract
from rag.runtime.generation_test_authorization import TestPublicationAuthorization


class TestOnlyAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/"codebridge-rag-generation-test"
        (self.root/"generations").mkdir(parents=True)
        create_bundle(self.root/"generations"/"one",
                      [("a","doc","hello"),("b","other","preserved")])
        create_bundle(self.root/"generations"/"two",
                      [("a","doc","updated"),("b","other","preserved")])
        activate_test_generation(self.root,"one")
        self.inputs=Path(self.temp.name)/"selected"
        self.inputs.mkdir()
        (self.inputs/"doc.md").write_text("updated",encoding="utf-8")
        self.snapshot=snapshot_preview("a",self.inputs,[{"path":"doc.md"}])
        self.contract=build_review_contract(self.snapshot,"a",self.inputs)

    def authorization(self):
        return TestPublicationAuthorization(
            self.root,"one","two","a",self.inputs,self.snapshot,self.contract)

    def test_confirmed_once_publishes_to_isolated_root(self):
        authorization=self.authorization()
        result=authorization.execute(confirmed=True,review_contract=self.contract,backup_name="before")
        self.assertEqual(result["state"],"BACKUP_GATED_TEST_PUBLICATION")
        self.assertEqual(resolve_generation(self.root).generation,"two")
        with self.assertRaisesRegex(ValueError,"consumed"):
            authorization.execute(confirmed=True,review_contract=self.contract,backup_name="again")

    def test_denied_confirmation_cannot_publish_or_be_reused(self):
        authorization=self.authorization()
        with self.assertRaisesRegex(ValueError,"explicit confirmation"):
            authorization.execute(confirmed=False,review_contract=self.contract,backup_name="before")
        self.assertEqual(resolve_generation(self.root).generation,"one")
        with self.assertRaisesRegex(ValueError,"consumed"):
            authorization.execute(confirmed=True,review_contract=self.contract,backup_name="before")

    def test_stale_snapshot_blocks_publish(self):
        authorization=self.authorization()
        (self.inputs/"doc.md").write_text("changed",encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"changed"):
            authorization.execute(confirmed=True,review_contract=self.contract,backup_name="before")
        self.assertEqual(resolve_generation(self.root).generation,"one")
        self.assertFalse((self.root/"backups"/"before").exists())

    def test_concurrent_same_authorization_only_one_execution(self):
        import threading
        from unittest.mock import patch
        import rag.runtime.generation_test_authorization as module
        authorization=self.authorization()
        entered=threading.Event()
        release=threading.Event()
        outcomes=[]
        original=module.publish_with_verified_backup
        def delayed(*args,**kwargs):
            entered.set()
            if not release.wait(6):
                raise TimeoutError("test did not release publication")
            return original(*args,**kwargs)
        def worker():
            try:
                outcomes.append(("first",authorization.execute(
                    confirmed=True,review_contract=self.contract,backup_name="before")))
            except Exception as exc:
                outcomes.append(("first",type(exc).__name__))
        with patch.object(module,"publish_with_verified_backup",side_effect=delayed) as publishing:
            thread=threading.Thread(target=worker,daemon=True)
            thread.start()
            try:
                self.assertTrue(entered.wait(4))
                with self.assertRaisesRegex(ValueError,"consumed"):
                    authorization.execute(confirmed=True,review_contract=self.contract,backup_name="again")
            finally:
                release.set()
                thread.join(9)
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(outcomes),1)
        self.assertIsInstance(outcomes[0][1],dict)
        self.assertEqual(publishing.call_count,1)
        self.assertEqual(resolve_generation(self.root).generation,"two")

    def test_publication_failure_consumes_authorization(self):
        from unittest.mock import patch
        import rag.runtime.generation_test_authorization as module
        authorization=self.authorization()
        with patch.object(module,"publish_with_verified_backup",
                          side_effect=RuntimeError("injected publication failure")) as publishing:
            with self.assertRaisesRegex(RuntimeError,"injected publication"):
                authorization.execute(confirmed=True,review_contract=self.contract,backup_name="before")
            with self.assertRaisesRegex(ValueError,"consumed"):
                authorization.execute(confirmed=True,review_contract=self.contract,backup_name="again")
        self.assertEqual(publishing.call_count,1)
        self.assertEqual(resolve_generation(self.root).generation,"one")

    def test_mismatched_review_receipt_consumes_authorization(self):
        authorization = self.authorization()
        different = dict(self.contract, review_sha256="0" * 64)
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            authorization.execute(confirmed=True, review_contract=different,
                                  backup_name="before")
        self.assertEqual(resolve_generation(self.root).generation, "one")
        self.assertFalse((self.root / "backups" / "before").exists())
        with self.assertRaisesRegex(ValueError, "consumed"):
            authorization.execute(confirmed=True, review_contract=self.contract,
                                  backup_name="before")

    def test_unreviewed_candidate_blocks_publication_and_backup(self):
        create_bundle(self.root/"generations"/"three",
                      [("a","doc","updated"),("a","extra","unreviewed"),
                       ("b","other","preserved")])
        authorization=TestPublicationAuthorization(
            self.root,"one","three","a",self.inputs,self.snapshot,self.contract)
        with self.assertRaisesRegex(ValueError,"unreviewed"):
            authorization.execute(confirmed=True,review_contract=self.contract,
                                  backup_name="blocked")
        self.assertEqual(resolve_generation(self.root).generation,"one")
        self.assertFalse((self.root/"backups"/"blocked").exists())
        with self.assertRaisesRegex(ValueError,"consumed"):
            authorization.execute(confirmed=True,review_contract=self.contract,
                                  backup_name="retry")

    def test_non_test_root_rejected(self):
        with self.assertRaisesRegex(ValueError,"isolated"):
            TestPublicationAuthorization(self.inputs,"one","two","a",
                                         self.inputs,self.snapshot,self.contract)

if __name__=="__main__":
    unittest.main()
