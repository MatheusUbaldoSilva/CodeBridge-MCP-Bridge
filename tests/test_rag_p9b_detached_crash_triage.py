import tempfile
import unittest
from pathlib import Path

from installer.rag_p9b_detached_crash_triage import triage_crash
from installer.rag_p9b_rollback_journal import RollbackJournal


class DetachedCrashTriageTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.journal=self.root/"tx.jsonl"
        j=RollbackJournal(self.journal)
        j("SHELL_DETACHED_LIFECYCLE_ARMED",
          {"transaction_sha256":"a"*64})
        j("SHELL_DETACHED_SHUTDOWN_SIGNALED",{})
        self.data=dict(installed=self.root/"installed",
          identity_manifest=self.root/"identity.json",
          identity_sha256="a"*64,
          source_commit="b"*40,journal_path=self.journal,
          identity_probe=lambda **kw:{
              "state":"DETACHED_IDENTITY_OBSERVED_ONLY",
              "identity_verified":True,"artifacts_checked":4},
          stop_probe=lambda *a:{
              "state":"POSTSTOP_OBSERVED_ONLY","observed_stopped":True})
    def test_incomplete_journal_is_review_not_execution(self):
        r=triage_crash(**self.data)
        self.assertEqual(r["state"],"DETACHED_CRASH_RECOVERY_REVIEW_REQUIRED")
        self.assertFalse(r["authorized"])
        self.assertFalse(r["recovery_executed"])
        self.assertEqual(r["journal_events"],2)
    def test_running_process_requires_review(self):
        r=triage_crash(**(self.data|{
            "stop_probe":lambda *a:{"state":"POSTSTOP_UNVERIFIED"}}))
        self.assertEqual(r["reason"],"PROCESSES_STILL_ACTIVE_OR_UNVERIFIED")
        self.assertFalse(r["authorized"])
    def test_wrong_identity_rejected_before_process_probe(self):
        r=triage_crash(**(self.data|{"identity_sha256":"c"*64}))
        self.assertEqual(r["reason"],"CRASH_TRIAGE_VALIDATION_FAILED")
    def test_missing_journal_refused(self):
        r=triage_crash(**(self.data|{
            "journal_path":self.root/"missing.jsonl"}))
        self.assertEqual(r["reason"],"JOURNAL_NOT_VERIFIED")
    def test_invalid_identity_does_not_probe_journal(self):
        r=triage_crash(**(self.data|{
            "identity_probe":lambda **kw:{"state":"IDENTITY_REFUSED"},
            "journal_probe":lambda *a: self.fail("journal unexpectedly read")}))
        self.assertEqual(r["reason"],"IDENTITY_NOT_BOUND")
    def test_terminal_journal_cannot_be_replayed(self):
        from installer.rag_p9b_rollback_journal import read_journal
        # A separate finalized combined journal must not be resumable.
        j=self.root/"complete.jsonl"
        done=RollbackJournal(j)
        done("SHELL_DETACHED_COMBINED_ARMED",{
            "transaction_sha256":"a"*64})
        done("SHELL_DETACHED_COMBINED_VERIFIED",{
            "postverified":True})
        r=triage_crash(**(self.data|{"journal_path":j}))
        self.assertEqual(r["reason"],"CRASH_TRIAGE_VALIDATION_FAILED")


if __name__=="__main__":unittest.main()
