import tempfile
import unittest
from pathlib import Path
from installer.rag_p9b_rollback_journal import RollbackJournal
from installer.rag_p9b_unified_journal_observer import observe_combined_transaction


class UnifiedReadOnlyObserverTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/"journal.jsonl"
        self.sha = "b"*64
        self.writer = RollbackJournal(self.path)
        self.writer("SHELL_DETACHED_COMBINED_ARMED",{"transaction_sha256": self.sha})

    def event(self, name, verified=True):
        self.writer(name,{"postverified":verified})

    def observe(self, **kwargs):
        return observe_combined_transaction(
            self.path, expected_transaction_sha256=kwargs.get("sha",self.sha))

    def complete(self):
        self.event("SHELL_DETACHED_FILES_VERIFIED")
        self.event("SHELL_DETACHED_SHELL_VERIFIED")
        self.event("SHELL_DETACHED_COMBINED_VERIFIED")

    def test_complete_sequence_observed_without_authorization(self):
        self.complete()
        result = self.observe()
        self.assertTrue(result["verified"])
        self.assertFalse(result["cutover_authorized"])
        self.assertTrue(result["read_only"])

    def test_incomplete_never_success(self):
        self.event("SHELL_DETACHED_FILES_VERIFIED")
        self.assertEqual(self.observe()["reason"],"TRANSACTION_INCOMPLETE")

    def test_wrong_identity_refused(self):
        self.complete()
        self.assertEqual(self.observe(sha="f"*64)["reason"],"TRANSACTION_IDENTITY_MISMATCH")

    def test_shell_before_files_refused(self):
        self.event("SHELL_DETACHED_SHELL_VERIFIED")
        self.event("SHELL_DETACHED_FILES_VERIFIED")
        self.event("SHELL_DETACHED_COMBINED_VERIFIED")
        self.assertEqual(self.observe()["reason"],"PHASE_ORDER_INVALID")

    def test_missing_postverify_refused(self):
        self.event("SHELL_DETACHED_FILES_VERIFIED", verified=False)
        self.event("SHELL_DETACHED_SHELL_VERIFIED")
        self.event("SHELL_DETACHED_COMBINED_VERIFIED")
        self.assertEqual(self.observe()["reason"],"POSTVERIFY_PROOF_MISSING")

    def test_duplicate_phase_event_refused(self):
        self.event("SHELL_DETACHED_FILES_VERIFIED")
        self.event("SHELL_DETACHED_FILES_VERIFIED")
        self.event("SHELL_DETACHED_SHELL_VERIFIED")
        self.event("SHELL_DETACHED_COMBINED_VERIFIED")
        self.assertEqual(self.observe()["reason"],"DUPLICATE_PHASE_EVENT")

    def test_extra_after_terminal_refused(self):
        self.complete()
        self.event("SHELL_DETACHED_COMBINED_EXCEPTION")
        self.assertEqual(self.observe()["reason"],"EVENT_AFTER_TERMINAL")

    def test_prior_failure_refused_even_with_terminal(self):
        self.event("SHELL_DETACHED_FILES_VERIFIED")
        self.event("SHELL_DETACHED_SHELL_UNVERIFIED")
        self.event("SHELL_DETACHED_SHELL_VERIFIED")
        self.event("SHELL_DETACHED_COMBINED_VERIFIED")
        self.assertEqual(self.observe()["reason"],"FAILURE_IN_JOURNAL")

    def test_truncated_journal_refused(self):
        self.complete()
        with self.path.open("ab") as stream:
            stream.write(b'{"seq":5')
        self.assertEqual(self.observe()["reason"],"JOURNAL_UNVERIFIED")


if __name__=="__main__":
    unittest.main()