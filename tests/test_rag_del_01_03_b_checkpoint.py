"""RAG-DEL-01.03-B durable receipts in temporary stage only."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch, Mock

from rag.runtime.knowledge_deletion_checkpoint import (
    checkpoint_survivor_batch,inspect_survivor_batch_checkpoint,
)
from rag.runtime.auto_index_incremental_plan import IncrementalPlanError


class SurvivorCheckpointTests(TestCase):
    def setUp(self):
        temp=TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path=Path(temp.name)
        self.client=Mock()
        self.bid="a"*32
        self.result={"state":"SURVIVOR_BATCH_READBACK_VERIFIED",
                     "vectors_verified":2,
                     "generation_activated":False,
                     "requires_durable_checkpoint":True}
        self.receipt={"candidate_vector_count":2,"vector_copy_authorized":False}
        self.sources={"sources":[]}

    def run_checkpoint(self,**changes):
        return checkpoint_survivor_batch(
            self.client,self.path,self.bid,self.result,self.receipt,self.sources,
            **{"operator_approved":True,**changes},
        )

    @patch("rag.runtime.knowledge_deletion_checkpoint.verify_isolated_reuse_batch")
    def test_receipt_written_and_recovered(self, verify):
        verify.return_value={"revalidation_passed":True,"checked_vectors":2}
        result=self.run_checkpoint()
        self.assertEqual(result["state"],"SURVIVOR_BATCH_DURABLY_VERIFIED")
        inspected=inspect_survivor_batch_checkpoint(self.path,self.bid)
        self.assertEqual(inspected["state"],"NEEDS_QDRANT_REVALIDATION")
        self.assertEqual(inspected["vectors_declared"],2)
        self.assertEqual(inspected["receipt_sha256"],result["receipt_sha256"])

    def test_no_approval_no_receipt(self):
        with self.assertRaises(PermissionError):
            self.run_checkpoint(operator_approved=False)
        self.assertEqual(list(self.path.iterdir()),[])

    def test_missing_post_copy_proof_no_receipt(self):
        self.result["state"]="UNVERIFIED"
        with self.assertRaises(IncrementalPlanError):
            self.run_checkpoint()
        self.assertEqual(list(self.path.iterdir()),[])

    def test_receipt_count_drift_denied(self):
        self.receipt["candidate_vector_count"]=3
        with self.assertRaises(IncrementalPlanError):
            self.run_checkpoint()
        self.assertEqual(list(self.path.iterdir()),[])

    @patch("rag.runtime.knowledge_deletion_checkpoint.verify_isolated_reuse_batch")
    def test_inconsistent_post_write_revalidation_denied(self,verify):
        verify.return_value={"revalidation_passed":True,"checked_vectors":1}
        with self.assertRaises(IncrementalPlanError):
            self.run_checkpoint()
        self.assertEqual(inspect_survivor_batch_checkpoint(self.path,self.bid)["state"],
                         "NEEDS_QDRANT_REVALIDATION")
