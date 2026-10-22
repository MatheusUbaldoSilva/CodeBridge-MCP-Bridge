import unittest
from installer.rag_p9b_supervised_transaction import assess_transaction,rehearse_transaction

class SupervisorTransactionTests(unittest.TestCase):
    def evidence(self):
        return {"artifacts_verified":True,"preimage_verified":True}
    def test_production_gate_requires_real_rollback(self):
        r=assess_transaction(release_evidence=self.evidence(),
            poststop_evidence={"state":"POSTSTOP_OBSERVED_ONLY","observed_stopped":True},
            rollback_evidence={"state":"UNIFIED_LAB_RECOVERED","verified":True},
            independent_channel=True)
        self.assertEqual(r["reason"],"PRODUCTION_ROLLBACK_NOT_PROVEN")
        self.assertFalse(r["authorized"])
    def test_positive_observation_never_authorizes_install(self):
        r=assess_transaction(release_evidence=self.evidence(),
            poststop_evidence={"state":"POSTSTOP_OBSERVED_ONLY","observed_stopped":True},
            rollback_evidence={"state":"PRODUCTION_ROLLBACK_VERIFIED","verified":True},
            independent_channel=True)
        self.assertEqual(r["state"],"TRANSACTION_GATES_OBSERVED_ONLY")
        self.assertFalse(r["authorized"])
    def test_valid_injected_lab_transaction(self):
        events=[]
        r=rehearse_transaction(release_evidence=self.evidence(),
            stop=lambda:{"verified":True},rollback=lambda:{"verified":True},
            restart=lambda:{"verified":True},external_ready=True,
            journal=lambda event,data:events.append(event))
        self.assertEqual(r["state"],"TRANSACTION_REHEARSAL_VERIFIED")
        self.assertEqual(len(events),4)
        self.assertFalse(r["production_modified"])
    def test_failed_rollback_blocks_restart(self):
        observed=[]
        r=rehearse_transaction(release_evidence=self.evidence(),
            stop=lambda:{"verified":True},rollback=lambda:{"verified":False},
            restart=lambda:observed.append("restart"),external_ready=True,
            journal=lambda event,data:None)
        self.assertEqual(r["reason"],"ROLLBACK_POSTVERIFY_FAILED")
        self.assertEqual(observed,[])
    def test_absent_external_channel_refuses(self):
        r=rehearse_transaction(release_evidence=self.evidence(),
            stop=lambda:{"verified":True},rollback=lambda:{"verified":True},
            restart=lambda:{"verified":True},external_ready=False,
            journal=lambda *a:None)
        self.assertEqual(r["reason"],"PRECONDITIONS_MISSING")
    def test_stop_exception_stays_review_required(self):
        def explode():raise OSError("injected")
        r=rehearse_transaction(release_evidence=self.evidence(),
            stop=explode,rollback=lambda:{"verified":True},
            restart=lambda:{"verified":True},external_ready=True,
            journal=lambda *a:None)
        self.assertEqual(r["state"],"TRANSACTION_REHEARSAL_REVIEW_REQUIRED")
if __name__=="__main__":unittest.main()
