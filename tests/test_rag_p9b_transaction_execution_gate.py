import unittest
from installer.rag_p9b_transaction_execution_gate import assess_execution_gate

class ExecutionGateTests(unittest.TestCase):
    def check(self,identity=True,stopped=True,journal=None):
        return assess_execution_gate(identity="manifest",identity_sha="a"*64,
             installed="installed",journal=journal,
             identity_probe=lambda *_:{"verified":identity,
                    "state":"TRANSACTION_IDENTITY_VERIFIED" if identity else "INVALID"},
             poststop_probe=lambda *_:{"observed_stopped":stopped,
                    "state":"POSTSTOP_OBSERVED_ONLY" if stopped else "BLOCKED"})
    def test_bound_transaction_and_stopped_but_not_authorized(self):
        r=self.check()
        self.assertEqual(r["state"],"P9B_EXECUTION_GATES_OBSERVED_ONLY")
        self.assertFalse(r["authorized"])
    def test_active_process_blocks(self):
        self.assertEqual(self.check(stopped=False)["reason"],"INDEPENDENT_POSTSTOP_UNVERIFIED")
    def test_invalid_identity_blocks(self):
        self.assertEqual(self.check(identity=False)["reason"],"BOUND_TRANSACTION_IDENTITY_INVALID")
    def test_recovery_journal_blocks(self):
        self.assertEqual(self.check(journal="pending")["reason"],"RECOVERY_JOURNAL_REQUIRES_REVIEW")
if __name__=="__main__":unittest.main()
