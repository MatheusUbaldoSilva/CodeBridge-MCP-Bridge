import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rag.runtime.offline_lab_evidence_summary import summarize_lab_evidence

P={"state":"EXPECTED_PIDS_ABSENT_UNPROVEN", "copy_authorized":False}
H={"state":"LAB_HANDLES_READABLE_UNPROVEN","files_checked":3,"copy_authorized":False}
R={"state":"LAB_RESTORE_EQUIVALENCE_UNPROVEN_FOR_PRODUCTION",
   "same_hashes":True,"same_semantic_content":True,
   "production_authorized":False,"publication_authorized":False}

class EvidenceSummaryTests(unittest.TestCase):
    def report(self, **kwargs):
        return summarize_lab_evidence(process_exit=kwargs.get("process",P),
          handle_probe=kwargs.get("handles",H),restore_audit=kwargs.get("restore",R),
          full_inventory=kwargs.get("inventory"))
    def test_successful_lab_still_blocks_production(self):
        r=self.report()
        self.assertTrue(r["evidence_complete"])
        self.assertEqual(r["state"],"LAB_EVIDENCE_COLLECTED_NO_PRODUCTION_PROOF")
        self.assertFalse(r["copy_authorized"])
        self.assertFalse(r["all_handles_closed"])
    def test_invalid_process_report_blocks(self):
        r=self.report(process={"state":"BLOCKED"})
        self.assertIn("PROCESS_EXIT_UNPROVEN",r["issues"])
        self.assertFalse(r["copy_authorized"])
    def test_missing_vector_files_blocks(self):
        r=self.report(handles={**H,"files_checked":2})
        self.assertIn("FILE_HANDLE_PROBE_UNPROVEN",r["issues"])
    def test_restore_corrupted_blocks(self):
        r=self.report(restore={**R,"same_semantic_content":False})
        self.assertIn("RESTORE_EQUIVALENCE_UNPROVEN",r["issues"])
    def test_claim_of_authorization_is_rejected(self):
        r=self.report(handles={**H,"copy_authorized":True})
        self.assertIn("handles_CLAIMS_AUTHORIZATION",r["issues"])
    def test_unverified_inventory_blocks(self):
        r=self.report(inventory={"identity_inventory_ok":False,"unverified_count":1})
        self.assertIn("FULL_PROCESS_INVENTORY_UNTRUSTED",r["issues"])
    def test_null_input_is_blocked(self):
        r=self.report(process=None)
        self.assertEqual(r["state"],"BLOCKED")
        self.assertFalse(r["copy_authorized"])
if __name__=="__main__": unittest.main()
