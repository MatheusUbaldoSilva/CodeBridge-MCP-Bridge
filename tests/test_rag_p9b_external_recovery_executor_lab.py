import tempfile,unittest,json
from pathlib import Path
from installer.rag_p9b_external_recovery_executor_lab import recover_externally

class ExternalTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.lab=self.root/"lab";self.lab.mkdir()
        (self.lab/"identity.json").write_text(json.dumps({
           "schema":1,"purpose":"P9B_DISPOSABLE_UNIFIED_LAB","file_sha":"bad"}))
        self.snapshot=self.root/"zip";self.snapshot.write_bytes(b"archive")
        self.kw={"lab_root":self.lab,"nsis_snapshot":self.snapshot,
                 "identity_file":"manifest","identity_sha":"a"*64,
                 "installed":self.root/"installed",
                 "identity_probe":lambda *_:{"verified":True}}
    def test_boolean_and_missing_schema_are_refused_before_recovery(self):
        for value in (True, None, "1"):
            with self.subTest(value=value):
                marker={"purpose":"P9B_DISPOSABLE_UNIFIED_LAB","file_sha":"bad"}
                if value is not None:
                    marker["schema"]=value
                (self.lab/"identity.json").write_text(json.dumps(marker),encoding="utf-8")
                report=recover_externally(**self.kw)
                self.assertEqual(report["reason"],"LAB_IDENTITY_INVALID")
                self.assertFalse(report["verified"])

    def test_symlink_lab_root_is_rejected_before_identity(self):
        link=self.root/"lab_link"
        try:
            link.symlink_to(self.lab,target_is_directory=True)
        except (OSError,NotImplementedError) as exc:
            self.skipTest(str(exc))
        report=recover_externally(**{**self.kw,"lab_root":link})
        self.assertEqual(report["reason"],"LAB_PATH_INVALID")
        self.assertFalse(report["verified"])

    def test_live_install_cannot_be_beneath_lab_root(self):
        report=recover_externally(**{**self.kw,
            "installed":self.lab/"nested"/"live-install"})
        self.assertEqual(report["reason"],"LAB_PATH_INVALID")
        self.assertFalse(report["verified"])

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
           "schema":1,"purpose":"P9B_DISPOSABLE_UNIFIED_LAB",
           "file_sha":hashlib.sha256(self.snapshot.read_bytes()).hexdigest()}))
        r=recover_externally(**{**self.kw,"recoverer":lambda *_:{
            "state":"UNIFIED_LAB_RECOVERED","recovered":True,
            "old_files_checked":236,"new_targets_removed":22,
            "shortcuts_checked":5,"fake_registry_keys_checked":2}})
        self.assertEqual(r["state"],"EXTERNAL_LAB_RECOVERY_VERIFIED")
        self.assertFalse(r["production_modified"])
    def test_malformed_recovery_counts_cannot_claim_success(self):
        import hashlib
        (self.lab/"identity.json").write_text(json.dumps({
            "schema":1,"purpose":"P9B_DISPOSABLE_UNIFIED_LAB",
            "file_sha":hashlib.sha256(self.snapshot.read_bytes()).hexdigest()}))
        for name,bad in (("old_files_checked",True),
                         ("new_targets_removed",-1),
                         ("shortcuts_checked",4),
                         ("fake_registry_keys_checked",None)):
            with self.subTest(name=name):
                proof={"state":"UNIFIED_LAB_RECOVERED","recovered":True,
                       "old_files_checked":236,"new_targets_removed":22,
                       "shortcuts_checked":5,"fake_registry_keys_checked":2}
                proof[name]=bad
                report=recover_externally(**{**self.kw,"recoverer":lambda *_:proof})
                self.assertEqual(report["reason"],"POSTVERIFY_COUNTS_INVALID")
                self.assertFalse(report["verified"])

    def test_failed_postverification_stays_blocked(self):
        import hashlib
        (self.lab/"identity.json").write_text(json.dumps({
           "schema":1,"purpose":"P9B_DISPOSABLE_UNIFIED_LAB",
           "file_sha":hashlib.sha256(self.snapshot.read_bytes()).hexdigest()}))
        r=recover_externally(**{**self.kw,"recoverer":lambda *_:{"state":"UNIFIED_LAB_POSTVERIFY_FAILED","recovered":False}})
        self.assertEqual(r["state"],"EXTERNAL_RECOVERY_REVIEW_REQUIRED")
if __name__=="__main__":unittest.main()
