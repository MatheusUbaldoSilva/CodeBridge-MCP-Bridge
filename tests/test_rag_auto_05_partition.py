"""RAG-AUTO-05-E deterministic bounded partition test."""
import unittest
from rag.runtime.auto_index_incremental_batches import partition_reuse_receipt
from rag.runtime.auto_index_incremental_plan import IncrementalPlanError


class PartitionTests(unittest.TestCase):
    def setUp(self):
        self.receipt={"mode":"CHUNK_RECEIPT_ONLY","project_id":"canary",
                      "candidate_vector_count":270,
                      "candidate_chunk_ids":{
                          "src/main.py":[f"c{i:03d}" for i in range(260)],
                          "docs/guide.md":[f"t{i:03d}" for i in range(10)],
                      }}
        self.approved={"sources":[
            {"path":"src/main.py","sha256":"a"*64,"index_kind":"CODE"},
            {"path":"docs/guide.md","sha256":"b"*64,"index_kind":"TEXT"},
        ]}

    def test_partition_never_crosses_model_or_exceeds_limit(self):
        batches=partition_reuse_receipt(self.receipt,self.approved)
        self.assertEqual(len(batches),3)
        self.assertEqual([b["batch_model"] for b in batches],["TEXT","CODE","CODE"])
        self.assertEqual([b["candidate_vector_count"] for b in batches],[10,256,4])
        self.assertFalse(any(b["vector_copy_authorized"] for b in batches))
        got=[c for part in batches for chunks in part["candidate_chunk_ids"].values()
             for c in chunks]
        expected=[c for chunks in self.receipt["candidate_chunk_ids"].values()
                  for c in chunks]
        self.assertEqual(set(got),set(expected))
        self.assertEqual(len(got),len(set(got)))

    def test_duplicates_and_count_drift_rejected(self):
        self.receipt["candidate_chunk_ids"]["src/main.py"][1]="c000"
        with self.assertRaises(IncrementalPlanError):
            partition_reuse_receipt(self.receipt,self.approved)
        self.receipt["candidate_chunk_ids"]["src/main.py"][1]="c001"
        self.receipt["candidate_vector_count"]=1
        with self.assertRaises(IncrementalPlanError):
            partition_reuse_receipt(self.receipt,self.approved)

    def test_malformed_configuration_denied(self):
        for limit in (0,257,True):
            with self.assertRaises(IncrementalPlanError):
                partition_reuse_receipt(self.receipt,self.approved,max_vectors=limit)
