"""DQ-E-F-3 aggregate never grants operation even with all observed true."""
from unittest import TestCase
from rag.runtime.knowledge_deletion_readiness_aggregate_dev import review_deletion_readiness_evidence_dev as review

def artifacts():
    return (dict(live_mcp_probe_attested=True,read_only=True,activation_authorized=False),
            dict(state="SUPERVISOR_REVIEW_BLOCKED_READ_ONLY",supervisor_observed_quiet=True,
                 blockers=[],read_only=True,queue_barrier_held=True),
            dict(state="DELETION_JOURNAL_INVENTORY_READ_ONLY_CLEAN",read_only=True,
                 activation_authorized=False))

class AggregateReviewDevTests(TestCase):
    def test_all_observations_cannot_authorize(self):
        r=review(*artifacts(),gui_runtime_attested=True,semantic_child_attested=True)
        self.assertEqual(r["state"],"EVIDENCE_REVIEW_ONLY")
        self.assertFalse(r["activation_authorized"])
        self.assertFalse(r["operational_use_allowed"])
        self.assertFalse(r["ready_for_operational_pilot"])
    def test_default_gui_child_missing(self):
        r=review(*artifacts())
        self.assertIn("gui_runtime_attested",r["blockers"])
        self.assertIn("semantic_child_attested",r["blockers"])
    def test_real_queue_job_blocks(self):
        a,b,c=artifacts()
        b["blockers"]=["UNRESOLVED_QUEUE_JOBS"]
        b["supervisor_observed_quiet"]=False
        b["queue_barrier_held"]=False
        self.assertIn("supervisor_queue_clean",review(a,b,c)["blockers"])
    def test_mcp_missing_blocks(self):
        a,b,c=artifacts()
        a["live_mcp_probe_attested"]=False
        self.assertIn("mcp_readonly_loaded",review(a,b,c)["blockers"])
    def test_journal_tamper_blocks(self):
        a,b,c=artifacts()
        c["state"]="DELETION_JOURNAL_REVIEW_BLOCKED"
        self.assertIn("journals_readonly_clean",review(a,b,c)["blockers"])
    def test_nonboolean_claims_rejected(self):
        for value in ("yes",1,None):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    review(*artifacts(),gui_runtime_attested=value)
    def test_missing_records_rejected(self):
        with self.assertRaises(ValueError):
            review({},None,{})
