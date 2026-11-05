"""Synthetic admission precheck tests: no operational channel, no live data."""
import copy
import unittest
from rag.runtime.knowledge_deletion_operational_admission_dev import (
    review_operational_deletion_admission as review, selection_sha256
)

class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.project="private_test"
        self.paths=["src/alpha.md","src/beta.md"]
        self.generation="scratch-v1"
        self.digest=selection_sha256(self.project,self.paths,self.generation)
        self.request=dict(project_id=self.project,selected_paths=self.paths,
                          generation=self.generation,selection_sha256=self.digest,
                          review_sha256="a"*64,catalog_sha256="b"*64,
                          public_pointer_sha256="c"*64,created_epoch=100,
                          operational_channel_attested=False,
                          operator_confirmation="RAG_DEL_REVIEW:"+self.project+":"+self.digest)
        self.gui=dict(state="GUI_LOADED_CODE_KERNEL_PINNED_READONLY",
                      installed_gui_loaded_code_observed=True,
                      expected_loaded_code_matches=True,peer_accesscheck_observed=True,
                      challenge_bound=True,expected_pid=42,observed_server_pid=42)
        self.inventory=dict(read_only=True,queue_pending_count=0,canary_count=0,
                            canary_catalog_consistent=True,
                            public_generation=self.generation,blockers=[])
    def run_review(self):
        return review(self.request,gui_witness=self.gui,
                      operational_inventory=self.inventory,now_epoch=120)

    def test_missing_real_operational_ipc_blocks(self):
        result=self.run_review()
        self.assertEqual(result["state"],"RAG_DEL_COMMAND_ADMISSION_BLOCKED")
        self.assertIn("OPERATIONAL_IPC_NOT_ATTESTED",result["blockers"])
        self.assertFalse(result["operational_use_allowed"])

    def test_even_fully_forged_green_receipts_never_authorize(self):
        self.request["operational_channel_attested"]=True
        result=self.run_review()
        self.assertEqual(result["state"],"RAG_DEL_COMMAND_ADMISSION_BLOCKED")
        self.assertIn("OPERATIONAL_IPC_NOT_ATTESTED",result["blockers"])
        self.assertFalse(result["activation_authorized"])
        self.assertFalse(result["deletion_enabled"])
        self.assertFalse(result["operational_use_allowed"])

    def test_selection_spoof_or_stale_review_blocked(self):
        self.request["operational_channel_attested"]=True
        self.request["selected_paths"]=["src/alpha.md"]
        self.assertIn("SELECTION_DIGEST_MISMATCH",self.run_review()["blockers"])
        self.request["selected_paths"]=self.paths
        self.request["created_epoch"]=-30
        self.assertIn("REVIEW_EXPIRED",self.run_review()["blockers"])

    def test_live_canary_or_queue_not_quiet(self):
        self.request["operational_channel_attested"]=True
        self.inventory["canary_count"]=1
        self.inventory["queue_pending_count"]=1
        self.assertIn("QUEUE_OR_CANARY_NOT_QUIET",self.run_review()["blockers"])

    def test_wrong_gui_birth_or_challenge_blocks(self):
        self.request["operational_channel_attested"]=True
        self.gui["challenge_bound"]=False
        self.assertIn("GUI_WITNESS_MISSING",self.run_review()["blockers"])

    def test_project_selection_confirmation_exact(self):
        self.request["operational_channel_attested"]=True
        self.request["operator_confirmation"]="RAG_DEL_REVIEW:private_test:"
        self.assertIn("PROJECT_AND_SELECTION_CONFIRMATION_MISSING",self.run_review()["blockers"])

    def test_public_and_traversal_rejected(self):
        with self.assertRaises(ValueError):
            selection_sha256("codebridge",self.paths,self.generation)
        for paths in (["../secret"],["/etc/passwd"],["src\\evil"],["src/a","src/a"],[],[{}],["a\nb"],["src//a"],["src/./a"],["src/../a"]):
            with self.subTest(paths=paths),self.assertRaises(ValueError):
                selection_sha256(self.project,paths,self.generation)

    def test_unstructured_receipts_fail_closed(self):
        self.assertEqual(review({},gui_witness=None,operational_inventory=None)["blockers"],
                         ["INVALID_RECEIPTS"])
