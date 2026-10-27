"""Opt-in RAG-AUTO-05 real Jina CODE vector reuse between approved canary stages."""
from contextlib import closing
from pathlib import Path
import os
import sqlite3
import tempfile
import unittest

from rag.runtime.auto_index_queue import create_draft,default_queue_path
from rag.runtime.auto_index_approval import build_auto_index_preview,approve_auto_index_draft
from rag.runtime.auto_index_staging import prepare_auto_staging
from rag.runtime.auto_index_batch import inventory_auto_vectors, _COLUMNS
from rag.runtime.production_index import _write_vectors
from rag.runtime.auto_index_incremental_read import read_reusable_vectors
from rag.runtime.auto_index_incremental_adapter import import_into_approved_auto_stage
from rag.runtime.auto_index_incremental_verify import verify_isolated_reuse_batch
from rag.index.qdrant_local import open_qdrant_local,close_qdrant_local


@unittest.skipUnless(os.environ.get("RAG_AUTO05_JINA_REAL")=="1",
                     "opt-in CUDA test only; no Jina model loaded by ordinary regression")
class JinaIncrementalTransferCanary(unittest.TestCase):
    def test_real_jina_code_embedding_reused_without_reembedding(self):
        with tempfile.TemporaryDirectory(prefix="ragauto05-jina-canary-") as temporary:
            base=Path(temporary)
            source=base/"sources"
            source.mkdir()
            (source/"one.py").write_text(
                "def test_incremental_vector():\n    return 42\n",encoding="utf-8")
            queue=default_queue_path(base)
            project="jina-incremental-canary"
            stages=[]
            jobs=[]
            for n in (1,2):
                draft=create_draft(
                    queue,project_id=project,source_root=source,
                    idempotency_key=f"real-jina-approve-{n}-12345678",
                    allow_write=True,
                )
                preview=build_auto_index_preview(project,source)
                approve_auto_index_draft(
                    queue,draft["job_id"],preview,
                    confirmed_digest=preview["review_sha256"],
                    operator_approved=True,allow_write=True,
                )
                prepared=prepare_auto_staging(
                    queue,draft["job_id"],operator_approved=True,
                    preparation_enabled=True,
                )
                stages.append(Path(prepared["stage"]))
                jobs.append(draft["job_id"])
            source_stage,target_stage=stages
            with closing(sqlite3.connect(
                (source_stage/"rag_index.sqlite3").as_uri()+"?mode=ro",uri=True,
            )) as cn:
                rows=cn.execute(
                    f"SELECT {_COLUMNS} FROM rag_chunks ORDER BY chunk_id"
                ).fetchall()
            self.assertGreater(len(rows),0)
            self.assertTrue(all(row[3]=="CODE" for row in rows))
            # This is the only Jina inference. It is isolated from the public index.
            _write_vectors(source_stage/"qdrant",project,[],rows,text_cpu_only=False)
            first=inventory_auto_vectors(queue,jobs[0])
            self.assertTrue(first["complete"])
            self.assertEqual(first["code_done"],len(rows))
            reviewed={"sources":[{
                "path":"one.py","sha256":rows[0][7],"index_kind":"CODE",
            }]}
            receipt={
                "mode":"CHUNK_RECEIPT_ONLY","project_id":project,
                "candidate_chunk_ids":{"one.py":[row[0] for row in rows]},
                "candidate_vector_count":len(rows),
                "vector_copy_authorized":False,
            }
            source_client=open_qdrant_local(source_stage/"qdrant")
            try:
                vectors=read_reusable_vectors(source_client,receipt,reviewed)
            finally:
                close_qdrant_local(source_client)
            self.assertEqual(len(vectors["CODE"]),len(rows))
            imported=import_into_approved_auto_stage(
                queue,jobs[1],receipt,reviewed,vectors,
                operator_approved=True,batch_id="e"*32,
            )
            self.assertEqual(imported["vectors_written"],len(rows))
            target_client=open_qdrant_local(target_stage/"qdrant")
            try:
                receipt_check=verify_isolated_reuse_batch(
                    target_client,target_stage,"e"*32,receipt,reviewed)
            finally:
                close_qdrant_local(target_client)
            self.assertTrue(receipt_check["revalidation_passed"])
            second=inventory_auto_vectors(queue,jobs[1])
            self.assertTrue(second["complete"])
            self.assertEqual(second["code_ids"],first["code_ids"])
            self.assertFalse(imported["public_pointer_updated"])
