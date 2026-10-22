import tempfile,unittest,json
from pathlib import Path
from installer.rag_p9b_external_recovery_executor_lab import recover_externally

class ExternalTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.lab=self.root/"lab";self.lab.mkdir()
        (self.lab/"identity.json").write_text(json.dumps({
           "purpose":"P9B_DISPOSABLE_UNIFIED_LAB","file_sha":"bad"}))
        self.snapshot=self.root/"zip";self.snapshot.write_bytes(b"archive")
        self.kw={"lab_root":self.lab,"nsis_snapshot":self.snapshot,
                 "identity_file":"manifest","identity_sha":"a"*64,
                 "installed":self.root/"installed",
                 "identity_probe":lambda *_:{"verified":True}}
    def test_real_identity_required(self):
        r=recover_externally(**{**self.kw,"identity_probe":lambda *_:{"verified":False}})
        self.assertEqual(r["reason"],"TRANSACTION_IDENTITY_UNVERIFIED")
    def test_snapshot_mismatch_required(self):
        r=recover_externally(**self.kw)
        self.assertEqual(r["reason"],"LAB_SNAPSHOT_MISMATCH")
    def test_unknown_lab_rejected(self):
        (self.lab/"identity.json").write_text("{}")
        self.assertEqual(recover_externally(**self.kw)["reason"],"LAB_IDENTITY_INVALID")
    def test_successful_recovery_must_report_verified(self):
        import hashlib
        (self.lab/"identity.json").write_text(json.dumps({
           "purpose":"P9B_DISPOSABLE_UNIFIED_LAB",
           "file_sha":hashlib.sha256(self.snapshot.read_bytes()).hexdigest()}))
        r=recover_externally(**{**self.kw,"recoverer":lambda *_:{
            "state":"UNIFIED_LAB_RECOVERED","recovered":True,
            "old_files_checked":236,"new_targets_removed":22,
            "shortcuts_checked":5,"fake_registry_keys_checked":2}})
        self.assertEqual(r["state"],"EXTERNAL_LAB_RECOVERY_VERIFIED")
        self.assertFalse(r["production_modified"])
    def test_failed_postverification_stays_blocked(self):
        import hashlib
        (self.lab/"identity.json").write_text(json.dumps({
           "purpose":"P9B_DISPOSABLE_UNIFIED_LAB",
           "file_sha":hashlib.sha256(self.snapshot.read_bytes()).hexdigest()}))
        r=recover_externally(**{**self.kw,"recoverer":lambda *_:{"state":"UNIFIED_LAB_POSTVERIFY_FAILED","recovered":False}})
        self.assertEqual(r["state"],"EXTERNAL_RECOVERY_REVIEW_REQUIRED")
if __name__=="__main__":unittest.main()
