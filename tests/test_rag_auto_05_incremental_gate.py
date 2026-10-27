"""RAG-AUTO-05-E isolated blueprint fail-closed tests."""
from __future__ import annotations

import unittest

from rag.runtime.auto_index_incremental_gate import build_incremental_execution_blueprint
from rag.runtime.auto_index_incremental_plan import IncrementalPlanError


class BlueprintTests(unittest.TestCase):
    def setUp(self):
        self.delta={"mode":"PLAN_ONLY","reuse_authorized":False,
                    "eligible_reuse_sources":["keep.py"],"reindex_sources":["change.py"],
                    "removed_sources":["deleted.py"]}
        self.chunks={"mode":"CHUNK_RECEIPT_ONLY","vector_copy_authorized":False,
                     "candidate_chunk_ids":{"keep.py":["chunk-one","chunk-two"]},
                     "candidate_vector_count":2}
        self.vectors={"mode":"VECTOR_RECEIPTS_VERIFIED","copy_executed":False,
                      "checked_vectors":2,"source_count":1}

    def check(self):
        return build_incremental_execution_blueprint(
            self.delta,self.chunks,self.vectors)

    def test_approved_receipts_make_only_inert_blueprint(self):
        result=self.check()
        self.assertEqual(result["reuse_vector_count"],2)
        self.assertEqual(result["work_items"],[{"path":"change.py","action":"EMBED"}])
        self.assertEqual(result["drop_sources"],["deleted.py"])
        self.assertFalse(result["stage_approved"])
        self.assertFalse(result["vectors_written"])
        self.assertFalse(result["public_pointer_updated"])

    def test_cross_receipt_vector_count_mismatch_denied(self):
        self.vectors["checked_vectors"]=1
        with self.assertRaises(IncrementalPlanError):
            self.check()

    def test_cross_receipt_paths_mismatch_denied(self):
        self.chunks["candidate_chunk_ids"]={"other.py":["chunk-one","chunk-two"]}
        with self.assertRaises(IncrementalPlanError):
            self.check()

    def test_reindex_reuse_overlap_denied(self):
        self.delta["reindex_sources"]=["keep.py"]
        with self.assertRaises(IncrementalPlanError):
            self.check()

    def test_duplicate_chunk_id_denied(self):
        self.chunks["candidate_chunk_ids"]["keep.py"]=["same","same"]
        with self.assertRaises(IncrementalPlanError):
            self.check()

    def test_prior_mutation_denied(self):
        self.vectors["copy_executed"]=True
        with self.assertRaises(IncrementalPlanError):
            self.check()
