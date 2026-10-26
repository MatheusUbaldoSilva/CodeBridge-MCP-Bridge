"""RAG-AUTO-02 worker acceptance with synthetic valid Qdrant vectors.

No Jina models or public RAG writes are performed by these tests.
"""
from contextlib import nullcontext
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from rag.runtime.auto_index_queue import create_draft,default_queue_path,get_job
from rag.runtime.auto_index_approval import build_auto_index_preview,approve_auto_index_draft
from rag.runtime.auto_index_batch import inventory_auto_vectors
from rag.runtime.auto_index_controls import request_auto_index_control
from rag.runtime.auto_index_worker import execute_auto_vector_batch
from rag.index.qdrant_local import (
    open_qdrant_local,close_qdrant_local,TEXT_VECTOR_COLLECTION,CODE_VECTOR_COLLECTION,
)
from rag.index.vector_ids import deterministic_vector_point_id
from rag.index.vector_namespace import vector_payload_with_namespace


def fake_writer(stage, project, text_rows, code_rows):
    from qdrant_client import models
    from rag.models.embedding import TEXT_EMBEDDING_DIMENSION
    from rag.models.code_embedding import CODE_EMBEDDING_DIMENSION
    client=open_qdrant_local(stage/"qdrant")
    try:
        for collection,rows,dimension in (
            (TEXT_VECTOR_COLLECTION,text_rows,TEXT_EMBEDDING_DIMENSION),
            (CODE_VECTOR_COLLECTION,code_rows,CODE_EMBEDDING_DIMENSION),
        ):
            points=[]
            for row in rows:
                payload=vector_payload_with_namespace(project,{
                    "document_id":row[1],"content":row[2],
                    "source_type":row[3],"path":row[4],"line_start":row[5],
                    "line_end":row[6],"sha256":row[7],"chunk_id":row[0],
                    "git_branch":row[8],"git_commit":row[9],
                })
                points.append(models.PointStruct(
                    id=deterministic_vector_point_id(project,collection,row[0]),
                    vector=[0.5]*dimension,payload=payload,
                ))
            if points:
                client.upsert(collection_name=collection,points=points,wait=True)
    finally:
        close_qdrant_local(client)


class AutoWorkerTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.source=self.root/"files"
        self.source.mkdir()
        (self.source/"README.md").write_text("CodeBridge automatic indexing\n",encoding="utf-8")
        (self.source/"module.py").write_text("def truth():\n  return True\n",encoding="utf-8")
        self.db=default_queue_path(self.root)
        self.project="auto-worker-demo"
        draft=create_draft(
            self.db,project_id=self.project,source_root=self.source,
            idempotency_key="test-worker-123456789",allow_write=True,
        )
        self.job=draft["job_id"]
        review=build_auto_index_preview(self.project,self.source)
        approve_auto_index_draft(
            self.db,self.job,review,confirmed_digest=review["review_sha256"],
            operator_approved=True,allow_write=True,
        )
        patcher=patch(
            "rag.runtime.auto_index_worker._public_generation",
            return_value="test_unchanged_generation",
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_batch(self,**kwargs):
        opts={
            "execute":True,"operator_approved":True,
            "confirmation":"RAG_AUTO_RUN:"+self.job,
            "memory_probe":lambda:4096,
            "semantic_guard_factory":nullcontext,
            "model_writer":fake_writer,
            "max_vectors":1,
        }
        opts.update(kwargs)
        return execute_auto_vector_batch(self.db,self.job,**opts)

    def test_approval_required_before_any_work(self):
        with self.assertRaises(PermissionError):
            self.run_batch(execute=False)
        self.assertEqual(get_job(self.db,self.job)["state"],"QUEUED")
        self.assertFalse(self.db.parent.parent.joinpath("staging").exists())

    def test_low_memory_defers_without_creating_stage(self):
        result=self.run_batch(memory_probe=lambda:1000)
        self.assertEqual(result["state"],"WAITING_FOR_MEMORY")
        self.assertEqual(get_job(self.db,self.job)["state"],"QUEUED")
        self.assertFalse(self.db.parent.parent.joinpath("staging").exists())

    def test_runs_text_then_code_and_marks_ready_only_after_validation(self):
        seen=[]
        for _ in range(10):
            out=self.run_batch()
            seen.append(out)
            assert out["index_published"] is False
            if out["state"]=="READY_FOR_REVIEW":
                break
        self.assertEqual(out["state"],"READY_FOR_REVIEW")
        self.assertEqual(out["vectors_done"],out["vectors_expected"])
        self.assertEqual(get_job(self.db,self.job)["state"],"READY_FOR_REVIEW")
        self.assertTrue(any(r["state"]=="QUEUED" for r in seen[:-1]))
        inventory=inventory_auto_vectors(self.db,self.job)
        self.assertTrue(inventory["complete"])
        stage=Path(inventory["stage"])
        progress=json.loads((stage/"progress.json").read_text(encoding="utf-8"))
        self.assertEqual(progress["total_vectors_done"],inventory["chunks"])
        self.assertFalse(progress["published"])

    def test_pause_requested_while_writer_is_active(self):
        def pause_writer(stage,project,text_rows,code_rows):
            request_auto_index_control(
                self.db,self.job,"PAUSE",operator_requested=True,
                control_enabled=True,
            )
            fake_writer(stage,project,text_rows,code_rows)
        out=self.run_batch(model_writer=pause_writer)
        self.assertEqual(out["state"],"PAUSED")
        self.assertEqual(out["vectors_done"],1)
        self.assertEqual(get_job(self.db,self.job)["state"],"PAUSED")
        request_auto_index_control(
            self.db,self.job,"RESUME",operator_requested=True,control_enabled=True,
        )
        self.assertEqual(get_job(self.db,self.job)["state"],"QUEUED")
        result=self.run_batch()
        self.assertGreaterEqual(result["vectors_done"],1)

    def test_partial_failure_keeps_confirmed_vectors_and_can_resume(self):
        def interrupted_writer(stage,project,text_rows,code_rows):
            fake_writer(stage,project,text_rows,code_rows)
            raise RuntimeError("simulated crash after Qdrant upsert")
        with self.assertRaisesRegex(RuntimeError,"simulated crash"):
            self.run_batch(model_writer=interrupted_writer)
        row=get_job(self.db,self.job)
        self.assertEqual(row["state"],"PAUSED")
        self.assertEqual(row["text_vectors_done"]+row["code_vectors_done"],1)
        request_auto_index_control(
            self.db,self.job,"RESUME",operator_requested=True,control_enabled=True,
        )
        replay=self.run_batch()
        self.assertEqual(replay["vectors_done"],2)
        self.assertEqual(replay["batch_vectors_requested"],1)

    def test_staging_stays_isolated_from_public_generation(self):
        self.run_batch()
        stage=Path(inventory_auto_vectors(self.db,self.job)["stage"])
        self.assertIn("auto",stage.parts)
        self.assertTrue(stage.exists())
        self.assertFalse((self.source/"rag_index.sqlite3").exists())


if __name__=="__main__":
    unittest.main()
