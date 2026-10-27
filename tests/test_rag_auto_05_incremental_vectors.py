"""RAG-AUTO-05-D: supplied Qdrant vector contract tests."""
from __future__ import annotations

import unittest

from rag.index.vector_ids import deterministic_vector_point_id
from rag.models.embedding import TEXT_EMBEDDING_DIMENSION
from rag.models.code_embedding import CODE_EMBEDDING_DIMENSION
from rag.runtime.auto_index_incremental_plan import IncrementalPlanError
from rag.runtime.auto_index_incremental_vectors import validate_reusable_point_records


class PointReuseTests(unittest.TestCase):
    def setUp(self):
        self.project="lab-project"
        self.approved={"sources":[
            {"path":"src/entry.py","sha256":"a"*64,"index_kind":"CODE"},
            {"path":"docs/guide.md","sha256":"b"*64,"index_kind":"TEXT"},
        ]}
        self.receipt={
            "mode":"CHUNK_RECEIPT_ONLY","project_id":self.project,
            "candidate_chunk_ids":{"src/entry.py":["code-id"],
                                   "docs/guide.md":["text-id"]},
            "vector_copy_authorized":False,
        }

    def point(self,kind):
        text=kind=="TEXT"
        chunk="text-id" if text else "code-id"
        path="docs/guide.md" if text else "src/entry.py"
        sha="b"*64 if text else "a"*64
        collection=kind.lower()
        return {
            "id":deterministic_vector_point_id(self.project,collection,chunk),
            "payload":{
                "project_namespace":self.project,"chunk_id":chunk,"path":path,
                "source_type":("DOCUMENTATION" if kind=="TEXT" else "CODE"),"sha256":sha,
            },
            "vector":[0.01]*(TEXT_EMBEDDING_DIMENSION if text else CODE_EMBEDDING_DIMENSION),
        }

    def run_check(self,records=None):
        if records is None:
            records={"TEXT":[self.point("TEXT")],"CODE":[self.point("CODE")]}
        return validate_reusable_point_records(self.receipt,self.approved,records)

    def test_two_verified_point_receipts_are_still_not_copied(self):
        result=self.run_check()
        self.assertEqual(result["checked_vectors"],2)
        self.assertFalse(result["copy_executed"])
        self.assertFalse(result["public_pointer_updated"])

    def test_missing_or_wrong_collection_fails(self):
        with self.assertRaises(IncrementalPlanError):
            self.run_check({"TEXT":[self.point("TEXT")],"CODE":[]})
        with self.assertRaises(IncrementalPlanError):
            self.run_check({"TEXT":[self.point("CODE")],"CODE":[self.point("TEXT")]})

    def test_foreign_payload_or_id_fails(self):
        for field,value in (("project_namespace","evil"),
                            ("path","different"),
                            ("sha256","c"*64)):
            with self.subTest(field=field):
                wrong=self.point("CODE")
                wrong["payload"][field]=value
                with self.assertRaises(IncrementalPlanError):
                    self.run_check({"TEXT":[self.point("TEXT")],"CODE":[wrong]})
        wrong=self.point("CODE")
        wrong["id"]="0"*36
        with self.assertRaises(IncrementalPlanError):
            self.run_check({"TEXT":[self.point("TEXT")],"CODE":[wrong]})

    def test_dimension_nan_bool_or_duplicate_denied(self):
        for values in ([0.0],[float("nan")]*CODE_EMBEDDING_DIMENSION,
                       [True]*CODE_EMBEDDING_DIMENSION):
            bad=self.point("CODE")
            bad["vector"]=values
            with self.assertRaises(IncrementalPlanError):
                self.run_check({"TEXT":[self.point("TEXT")],"CODE":[bad]})
        bad=self.point("CODE")
        with self.assertRaises(IncrementalPlanError):
            self.run_check({"TEXT":[self.point("TEXT")],"CODE":[bad,bad]})

    def test_log_file_requires_log_payload_classification(self):
        import copy
        original=self.receipt
        prior=self.approved
        self.receipt={
            "mode":"CHUNK_RECEIPT_ONLY","project_id":self.project,
            "candidate_chunk_ids":{"notes.txt":["log-chunk"]},
            "vector_copy_authorized":False,
        }
        self.approved={"sources":[
            {"path":"notes.txt","sha256":"e"*64,"index_kind":"TEXT"},
        ]}
        record=self.point("TEXT")
        record["id"]=deterministic_vector_point_id(
            self.project,"text","log-chunk")
        record["payload"]={
            "project_namespace":self.project,"chunk_id":"log-chunk",
            "path":"notes.txt","sha256":"e"*64,"source_type":"LOG",
        }
        try:
            self.assertEqual(self.run_check({"TEXT":[record],"CODE":[]})["checked_vectors"],1)
            record["payload"]["source_type"]="DOCUMENTATION"
            with self.assertRaises(IncrementalPlanError):
                self.run_check({"TEXT":[record],"CODE":[]})
        finally:
            self.receipt=original
            self.approved=prior

    def test_untrusted_receipt_denied(self):
        bad={**self.receipt,"vector_copy_authorized":True}
        with self.assertRaises(IncrementalPlanError):
            validate_reusable_point_records(bad,self.approved,{})
