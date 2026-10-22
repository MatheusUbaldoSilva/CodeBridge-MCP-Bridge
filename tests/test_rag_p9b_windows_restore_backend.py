import hashlib
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from installer.rag_p9b_shell_snapshot import snapshot_shell_state
from installer.rag_p9b_windows_restore_backend import restore_shell


class FakeRegistry:
    def __init__(self):
        self.keys={}
        self.fail=False
    def read_key(self,key):
        return self.keys.get(key,{"exists":False,"values":{}})
    def replace_key(self,key,value):
        if self.fail:
            self.fail=False
            raise OSError("injected registry failure")
        self.keys[key]=value


class BackendTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=Path(t.name)
        self.appdata=self.root/"roaming"
        self.desktop=self.root/"desktop"
        self.desktop.mkdir()
        self.menu=self.appdata/"Microsoft"/"Windows"/"Start Menu"/"Programs"/"CodeBridge"
        self.menu.mkdir(parents=True)
        self.link=self.menu/"CodeBridge.lnk"
        self.link.write_bytes(b"old-link")
        self.snapshot=self.root/"shell.zip"
        snapshot_shell_state(appdata=self.appdata,desktop=self.desktop,
            snapshot=self.snapshot,registry_values=lambda k,n:{"exists":True,"values":{}})
        self.registry=FakeRegistry()
        self.logs=[]

    def run_it(self,**kwargs):
        options=dict(snapshot=self.snapshot,expected_sha256=hashlib.sha256(self.snapshot.read_bytes()).hexdigest(),appdata=self.appdata,desktop=self.desktop,
                     registry=self.registry,installed=self.root,
                     process_guard=lambda _:{"state":"NO_RUNNING_CODEBRIDGE"},
                     preimage="proof.zip",preimage_sha256="a"*64,
                     preimage_verifier=lambda *a:{"state":"CRASH_PREIMAGE_VERIFIED","verified":True},
                     stopped=True,external=True,execute=True,
                     journal=lambda *x:self.logs.append(x))
        options.update(kwargs)
        return restore_shell(**options)

    def test_disabled(self):
        self.assertEqual(self.run_it(execute=False)["reason"],
                         "EXPLICIT_INDEPENDENT_STOPPED_GATES_REQUIRED")

    def test_synthetic_restore_requires_postverify(self):
        self.link.write_bytes(b"new-link")
        r=self.run_it()
        self.assertEqual(r["state"],"SHELL_BACKEND_APPLIED_POSTVERIFY_REQUIRED")
        self.assertFalse(r["verified"])
        self.assertEqual(self.link.read_bytes(),b"old-link")

    def test_registry_failure_compensation(self):
        self.link.write_bytes(b"new-link")
        self.registry.fail=True
        r=self.run_it()
        self.assertEqual(r["state"],"SHELL_BACKEND_RECOVERY_REVIEW_REQUIRED")
        self.assertTrue(r["rollback_attempted"])
        self.assertTrue(r["compensation_verified"])
        self.assertEqual(self.link.read_bytes(),b"new-link")

    def test_wrong_snapshot_digest_refused(self):
        self.link.write_bytes(b"live")
        r=self.run_it(expected_sha256="f"*64)
        self.assertEqual(r["reason"],"SNAPSHOT_DIGEST_MISMATCH")
        self.assertEqual(self.link.read_bytes(),b"live")

    def test_partially_written_link_is_compensated(self):
        self.link.write_bytes(b"before-transaction")
        ordinary=Path.write_bytes
        failed=[False]
        target=self.link
        def interrupted(file,data):
            if Path(file)==target and not failed[0]:
                failed[0]=True
                ordinary(file,b"partial")
                raise OSError("INJECTED_AFTER_PARTIAL_WRITE")
            return ordinary(file,data)
        with patch.object(Path,"write_bytes",interrupted):
            r=self.run_it()
        self.assertTrue(failed[0])
        self.assertEqual(r["state"],"SHELL_BACKEND_RECOVERY_REVIEW_REQUIRED")
        self.assertTrue(r["compensation_verified"])
        self.assertEqual(self.link.read_bytes(),b"before-transaction")

    def test_journal_failure_does_not_skip_compensation(self):
        self.link.write_bytes(b"new-link")
        self.registry.fail=True
        def journal(state,detail):
            if state=="SHELL_BACKEND_PARTIAL_FAILURE":
                raise OSError("disk journal failed")
        r=self.run_it(journal=journal)
        self.assertEqual(r["state"],"SHELL_BACKEND_RECOVERY_REVIEW_REQUIRED")
        self.assertIn("JOURNAL_WRITE_FAILED",r["compensation_errors"])
        self.assertEqual(self.link.read_bytes(),b"new-link")

    def test_process_guard_blocks_active_gui(self):
        self.link.write_bytes(b"live")
        r=self.run_it(process_guard=lambda _:{"state":"UPDATE_PROCESS_BLOCKED"})
        self.assertEqual(r["reason"],"CODEBRIDGE_PROCESS_STILL_ACTIVE")
        self.assertEqual(self.link.read_bytes(),b"live")

    def test_missing_preimage_refuses_mutation(self):
        self.link.write_bytes(b"live")
        r=self.run_it(preimage=None)
        self.assertEqual(r["reason"],"DURABLE_PREIMAGE_REQUIRED")
        self.assertEqual(self.link.read_bytes(),b"live")

    def test_unverified_preimage_refuses_mutation(self):
        self.link.write_bytes(b"live")
        r=self.run_it(preimage_verifier=lambda *a:{"verified":False})
        self.assertEqual(r["reason"],"DURABLE_PREIMAGE_UNVERIFIED")
        self.assertEqual(self.link.read_bytes(),b"live")

    def test_external_channel_required(self):
        r=self.run_it(external=False)
        self.assertEqual(r["reason"],"EXPLICIT_INDEPENDENT_STOPPED_GATES_REQUIRED")

    def test_snapshot_corrupt_blocks_mutation(self):
        self.link.write_bytes(b"live-new")
        self.snapshot.write_bytes(b"bad zip")
        r=self.run_it()
        self.assertEqual(r["reason"],"SNAPSHOT_UNVERIFIED")
        self.assertEqual(self.link.read_bytes(),b"live-new")

    def test_reject_symlink(self):
        self.link.unlink()
        try:self.link.symlink_to(self.snapshot)
        except OSError:self.skipTest("symlinks disabled")
        r=self.run_it()
        self.assertEqual(r["reason"],"UNTRUSTED_DESTINATION")


if __name__=="__main__":
    unittest.main()
