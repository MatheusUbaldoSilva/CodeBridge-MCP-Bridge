import unittest
from installer.rag_p9b_crash_recovery_gate import inspect_crash_recovery


class CrashGateTests(unittest.TestCase):
    def gate(self,*,snapshot=True,events=2,last="SHELL_BACKEND_WRITTEN",
             process="NO_RUNNING_CODEBRIDGE"):
        return inspect_crash_recovery(
            preimage="unused",preimage_sha="a"*64,journal="unused",
            installed="unused",
            preimage_verifier=lambda *args:{"verified":snapshot},
            journal_reader=lambda *args:{"state":"JOURNAL_OBSERVED_ONLY",
                                        "count":events,"last_state":last},
            process_guard=lambda *args:{"state":process})

    def test_interrupted_transaction_requires_review(self):
        r=self.gate()
        self.assertEqual(r["state"],"CRASH_RESTORATION_REVIEW_REQUIRED")
        self.assertFalse(r["recovery_authorized"])

    def test_running_gui_blocks(self):
        self.assertEqual(self.gate(process="UPDATE_PROCESS_BLOCKED")["reason"],
                         "CODEBRIDGE_STILL_ACTIVE")

    def test_snapshot_mismatch_blocks(self):
        self.assertEqual(self.gate(snapshot=False)["reason"],"PREIMAGE_UNVERIFIED")

    def test_terminal_journal_does_not_restart(self):
        self.assertEqual(self.gate(last="SHELL_RESTORE_VERIFIED")["state"],
                         "RECOVERY_ALREADY_VERIFIED_ONLY")

    def test_unfamiliar_state_blocks(self):
        self.assertEqual(self.gate(last="INVENTED")["reason"],
                         "UNKNOWN_LAST_JOURNAL_STATE")

    def test_boolean_and_noninteger_counts_are_rejected(self):
        for value in (True, False, "2", 2.0, None):
            with self.subTest(value=value):
                result=self.gate(events=value)
                self.assertEqual(result["reason"],"JOURNAL_UNVERIFIED")
                self.assertFalse(result["recovery_authorized"])

    def test_empty_journal_blocks(self):
        self.assertEqual(self.gate(events=0)["reason"],"EMPTY_JOURNAL")


if __name__=="__main__":
    unittest.main()
