"""RAG-AUTO-02.3: skip existing vectors and cross-verify Qdrant."""
from pathlib import Path
import tempfile
import unittest

from rag.runtime.auto_index_queue import create_draft,default_queue_path,AutoIndexQueueError
from rag.runtime.auto_index_approval import build_auto_index_preview,approve_auto_index_draft
from rag.runtime.auto_index_staging import prepare_auto_staging
from rag.runtime.auto_index_batch import inventory_auto_vectors,select_auto_vector_batch
from rag.index.qdrant_local import (
    open_qdrant_local,close_qdrant_local,TEXT_VECTOR_COLLECTION,CODE_VECTOR_COLLECTION,
)
from rag.index.vector_ids import deterministic_vector_point_id
from rag.index.vector_namespace import vector_payload_with_namespace


class AutoVectorBatchTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base=Path(temp.name)
        self.source=self.base/"source"
        self.source.mkdir()
        (self.source/"README.md").write_text("Build the CodeBridge project\n",encoding="utf-8")
        (self.source/"module.py").write_text("def answer():\n    return 42\n",encoding="utf-8")
        self.db=default_queue_path(self.base)
        self.project="auto-batch-test"
        job=create_draft(
            self.db,project_id=self.project,source_root=self.source,
            idempotency_key="batch-test-12345678",allow_write=True,
        )
        self.job=job["job_id"]
        preview=build_auto_index_preview(self.project,self.source)
        approve_auto_index_draft(
            self.db,self.job,preview,confirmed_digest=preview["review_sha256"],
            operator_approved=True,allow_write=True,
        )
        self.stage=Path(prepare_auto_staging(
            self.db,self.job,operator_approved=True,preparation_enabled=True,
        )["stage"])

    def _add_mock_point(self,row,*,collection):
        from qdrant_client import models
        from rag.models.embedding import TEXT_EMBEDDING_DIMENSION
        from rag.models.code_embedding import CODE_EMBEDDING_DIMENSION
        dimension=(CODE_EMBEDDING_DIMENSION if collection==CODE_VECTOR_COLLECTION
                   else TEXT_EMBEDDING_DIMENSION)
        payload=vector_payload_with_namespace(self.project,{
            "document_id":row[1],"content":row[2],"source_type":row[3],
            "path":row[4],"line_start":row[5],"line_end":row[6],
            "sha256":row[7],"chunk_id":row[0],
            "git_branch":row[8],"git_commit":row[9],
        })
        client=open_qdrant_local(self.stage/"qdrant")
        try:
            client.upsert(collection_name=collection,points=[
                models.PointStruct(
                    id=deterministic_vector_point_id(self.project,collection,row[0]),
                    vector=[0.25]*dimension,payload=payload,
                )
            ],wait=True)
        finally:
            close_qdrant_local(client)

    def test_empty_staging_counts_zero(self):
        status=inventory_auto_vectors(self.db,self.job)
        self.assertEqual(status["total_done"],0)
        self.assertEqual(status["chunks"],status["expected_text"]+status["expected_code"])
        self.assertFalse(status["complete"])

    def test_first_selects_only_one_model_and_excludes_persisted(self):
        first=select_auto_vector_batch(self.db,self.job,prefer="CODE")
        self.assertEqual(first["collection"],"CODE")
        self.assertLessEqual(len(first["rows"]),256)
        chosen=first["rows"][0]
        self._add_mock_point(chosen,collection=CODE_VECTOR_COLLECTION)
        next_batch=select_auto_vector_batch(self.db,self.job,prefer="CODE")
        self.assertNotIn(chosen[0],{row[0] for row in next_batch["rows"]})
        seen=inventory_auto_vectors(self.db,self.job)
        self.assertEqual(seen["code_done"],1)
        self.assertEqual(seen["text_done"],0)

    def test_rejects_corrupted_vector_payload(self):
        sample=select_auto_vector_batch(self.db,self.job,prefer="TEXT")["rows"][0]
        self._add_mock_point(sample,collection=TEXT_VECTOR_COLLECTION)
        self._write_bad_payload(sample)
        with self.assertRaises(AutoIndexQueueError):
            inventory_auto_vectors(self.db,self.job)

    def _write_bad_payload(self,row):
        from qdrant_client import models
        client=open_qdrant_local(self.stage/"qdrant")
        try:
            client.set_payload(
                collection_name=TEXT_VECTOR_COLLECTION,
                payload={"sha256":"tampered"},
                points=[deterministic_vector_point_id(self.project,TEXT_VECTOR_COLLECTION,row[0])],
                wait=True,
            )
        finally:
            close_qdrant_local(client)

    def test_rejects_unsafe_batch_arguments(self):
        with self.assertRaises(ValueError):
            select_auto_vector_batch(self.db,self.job,max_vectors=257)
        with self.assertRaises(ValueError):
            select_auto_vector_batch(self.db,self.job,max_vectors=0)
        with self.assertRaises(ValueError):
            select_auto_vector_batch(self.db,self.job,prefer="ALL")


if __name__=="__main__":
    unittest.main()
