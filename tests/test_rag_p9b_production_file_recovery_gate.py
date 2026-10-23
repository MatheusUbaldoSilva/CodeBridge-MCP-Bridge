import hashlib
import tempfile
import unittest
from pathlib import Path

from installer.rag_p9b_production_file_recovery_gate import assess_file_recovery


class RecoveryGateTests(unittest.TestCase):
    def setUp(self):
        d=tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.root=Path(d.name)
        self.installed=self.root/"installed"
        self.installed.mkdir()
        self.backup=self.root/"backup.zip"
        self.backup.write_bytes(b"synthetic backup")
        self.good_hash=hashlib.sha256(self.backup.read_bytes()).hexdigest()
        self.calls=[]
        self.kw=dict(
            installed=self.installed,snapshot=self.backup,
            snapshot_sha256=self.good_hash,preimage=self.root/"preimage.zip",
            preimage_sha256="a"*64,journal_path=self.root/"journal",
            expected_new_hashes={"rag/new.py":"b"*64},independent=True,
            snapshot_probe=lambda *a: {"verified":True,"state":"INSTALLER_ROLLBACK_SNAPSHOT_VERIFIED"},
            preimage_probe=lambda *a: {"verified":True,"state":"CRASH_PREIMAGE_VERIFIED"},
            journal_probe=lambda *a: {"state":"JOURNAL_OBSERVED_ONLY","last_state":"SHELL_NSIS_FULL_SCOPE_INTERRUPTED","count":2},
            journal_resume_probe=lambda *a: object(),
            poststop_probe=lambda *a: {"state":"POSTSTOP_OBSERVED_ONLY","observed_stopped":True},
            new_targets_probe=lambda *a,**k: {"state":"NEW_TARGETS_CONTENT_VERIFIED","ownership_evidence_verified":True,"delete_authorized":False})
    def test_all_evidence_is_only_read_only_observation(self):
        r=assess_file_recovery(**self.kw)
        self.assertEqual(r["state"],"PRODUCTION_FILE_ROLLBACK_GATES_OBSERVED_ONLY")
        self.assertFalse(r["verified"])
        self.assertFalse(r["delete_authorized"])
        self.assertFalse(r["installed_modified"])
    def test_independent_required(self):
        r=assess_file_recovery(**(self.kw|{"independent":False}))
        self.assertEqual(r["reason"],"INDEPENDENT_RUNTIME_REQUIRED")
    def test_tampered_snapshot_refused(self):
        r=assess_file_recovery(**(self.kw|{"snapshot_sha256":"f"*64}))
        self.assertEqual(r["reason"],"SNAPSHOT_SHA256_INVALID")
    def test_live_mcp_refused(self):
        r=assess_file_recovery(**(self.kw|{"poststop_probe":lambda *a:{"state":"POSTSTOP_UNVERIFIED","observed_stopped":False}}))
        self.assertEqual(r["reason"],"STOPPED_PROCESS_PROOF_MISSING")
    def test_missing_new_content_proof_refused(self):
        r=assess_file_recovery(**(self.kw|{"new_targets_probe":lambda *a,**k:{"state":"NEW_TARGETS_OBSERVED_ONLY"}}))
        self.assertEqual(r["reason"],"NEW_TARGET_OWNERSHIP_UNVERIFIED")
    def test_incomplete_file_restore_journal_can_be_rechecked(self):
        r=assess_file_recovery(**(self.kw|{
            "journal_probe":lambda *a:{
                "state":"JOURNAL_OBSERVED_ONLY",
                "last_state":"SHELL_PRODUCTION_FILE_BEFORE_UNLINK",
                "count":4}}))
        self.assertEqual(r["state"],"PRODUCTION_FILE_ROLLBACK_GATES_OBSERVED_ONLY")

    def test_invalid_resume_history_refused(self):
        def invalid(*args):
            raise ValueError("invalid initial journal state")
        r=assess_file_recovery(**(self.kw|{"journal_resume_probe":invalid}))
        self.assertEqual(r["reason"],"FILE_RECOVERY_PREFLIGHT_EXCEPTION")

    def test_journal_without_interrupt_refused(self):
        r=assess_file_recovery(**(self.kw|{"journal_probe":lambda *a:{"state":"JOURNAL_OBSERVED_ONLY","last_state":"SHELL_COMBINED_RECOVERY_VERIFIED","count":3}}))
        self.assertEqual(r["reason"],"INTERRUPTED_JOURNAL_UNVERIFIED")

if __name__=="__main__":
    unittest.main()
