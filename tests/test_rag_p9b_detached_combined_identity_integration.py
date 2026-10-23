"""Identity must be verified from real durable four-artifact fixture."""
import tempfile
import unittest
from pathlib import Path
from installer.rag_p9b_transaction_identity import NAMES,write_identity
from installer.rag_p9b_detached_combined_recovery import recover_detached_combined


class IdentityInCoordinatorTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.installed=self.root/"installed"
        self.installed.mkdir()
        items={}
        for name in NAMES:
            path=self.root/(name+".bin")
            path.write_bytes(("bound-"+name).encode())
            items[name]=path
        self.installer=items["installer"]
        self.identity=self.root/"identity.json"
        self.commit="a"*40
        saved=write_identity(self.identity,artifacts=items,
                             installed=self.installed,source_commit=self.commit)
        self.assertTrue(saved["written"])
        self.digest=saved["manifest_sha256"]
        self.events=[]
        self.kwargs=dict(
            independent=True,execute=True,production=True,
            identity_manifest=self.identity,identity_sha256=self.digest,
            installed=self.installed,source_commit=self.commit,
            file_worker=lambda: self.events.append("files") or {
                "state":"DETACHED_FILES_RESTORED_SHELL_PENDING",
                "verified":True,"shell_restore_required":True},
            shell_worker=lambda: self.events.append("shell") or {
                "state":"SHELL_RESTORE_VERIFIED","restored":True},
            verify_worker=lambda: self.events.append("postverify") or {"verified":True},
            journal=lambda *a:self.events.append("journal"),
            poststop_probe=lambda *a:{
                "state":"POSTSTOP_OBSERVED_ONLY","observed_stopped":True})

    def test_real_identity_checks_before_workers(self):
        result=recover_detached_combined(**self.kwargs)
        self.assertEqual(result["state"],"DETACHED_COMBINED_RESTORE_VERIFIED")
        self.assertEqual(self.events.count("files"),1)
        self.assertEqual(self.events.count("shell"),1)
        self.assertFalse(result["cutover_authorized"])

    def test_modified_installer_halts_before_journal(self):
        self.installer.write_bytes(b"foreign")
        result=recover_detached_combined(**self.kwargs)
        self.assertEqual(result["reason"],"BOUND_TRANSACTION_IDENTITY_REQUIRED")
        self.assertEqual(self.events,[])

    def test_live_process_halts_after_identity_before_journal(self):
        result=recover_detached_combined(**(self.kwargs|{
            "poststop_probe":lambda *a:{
                "state":"POSTSTOP_UNVERIFIED","observed_stopped":False}}))
        self.assertEqual(result["reason"],"INDEPENDENT_POSTSTOP_REQUIRED")
        self.assertEqual(self.events,[])

    def test_wrong_source_commit_does_not_start_rollback(self):
        result=recover_detached_combined(**(self.kwargs|{"source_commit":"b"*40}))
        self.assertEqual(result["reason"],"BOUND_TRANSACTION_IDENTITY_REQUIRED")
        self.assertEqual(self.events,[])


if __name__=="__main__":
    unittest.main()
