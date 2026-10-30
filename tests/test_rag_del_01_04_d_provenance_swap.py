from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch,Mock
from rag.runtime.knowledge_deletion_provenance_swap_lab import laboratory_provenance_gated_swap,DeletionEvidenceGateError

class ProvenanceSwapLabTests(TestCase):
    def setUp(self):
        t=TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=Path(t.name)
        self.row={"project_id":"demo","index_family":"RAG_DEL_01",
                  "generation_directory":str(self.root/"candidate")}
        self.preview={"project_id":"demo"}
        self.args={"catalog_file":self.root/"project-indexes.json",
                   "public_pointer":self.root/"public.json",
                   "source_snapshot_root":self.root/"snapshots",
                   "laboratory_mode":True,"operator_approved":True}
    def call(self,**kwargs):
        return laboratory_provenance_gated_swap(
            "demo","old",self.row,self.preview,
            self.root/"baseline.json",Mock(),**{**self.args,**kwargs})
    @patch("rag.runtime.knowledge_deletion_provenance_swap_lab.laboratory_verified_swap")
    @patch("rag.runtime.knowledge_deletion_provenance_swap_lab.audit_private_removal_candidate")
    def test_provenance_required_before_swap(self,audit,swap):
        audit.return_value={"state":"PRIVATE_REMOVAL_AUDIT_ONLY",
            "activation_authorized":False,"catalog_modified":False,
            "lineage_sha256":"a"*64,"vectors_verified":7,
            "snapshot_inventory_sha256":"b"*64}
        swap.return_value={"state":"LAB_SWAP_ACTIVE","operational_use_allowed":False}
        result=self.call()
        self.assertEqual(result["semantic_vectors_checked"],7)
        self.assertFalse(result["operational_use_allowed"])
        audit.assert_called_once()
        swap.assert_called_once()
    @patch("rag.runtime.knowledge_deletion_provenance_swap_lab.laboratory_verified_swap")
    @patch("rag.runtime.knowledge_deletion_provenance_swap_lab.audit_private_removal_candidate")
    def test_provenance_failure_prevents_catalog_swap(self,audit,swap):
        audit.side_effect=ValueError("unlisted survivor")
        with self.assertRaises(ValueError):self.call()
        swap.assert_not_called()
    @patch("rag.runtime.knowledge_deletion_provenance_swap_lab.laboratory_verified_swap")
    @patch("rag.runtime.knowledge_deletion_provenance_swap_lab.audit_private_removal_candidate")
    def test_incomplete_proof_denied(self,audit,swap):
        audit.return_value={"state":"PRIVATE_REMOVAL_AUDIT_ONLY",
            "activation_authorized":True,"catalog_modified":False}
        with self.assertRaises(DeletionEvidenceGateError):self.call()
        swap.assert_not_called()
    @patch("rag.runtime.knowledge_deletion_provenance_swap_lab.laboratory_verified_swap")
    def test_no_approval_does_not_call_swap(self,swap):
        with self.assertRaises(PermissionError):self.call(operator_approved=False)
        swap.assert_not_called()
    @patch("rag.runtime.knowledge_deletion_provenance_swap_lab.laboratory_verified_swap")
    def test_wrong_project_does_not_call_swap(self,swap):
        self.row["project_id"]="foreign"
        with self.assertRaises(DeletionEvidenceGateError):self.call()
        swap.assert_not_called()
