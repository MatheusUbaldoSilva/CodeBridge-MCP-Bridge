"""RAG-AUTO-05-E real approved queue staging (synthetic vector, no Jina)."""
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from rag.runtime.auto_index_queue import create_draft,default_queue_path
from rag.runtime.auto_index_approval import build_auto_index_preview,approve_auto_index_draft
from rag.runtime.auto_index_staging import prepare_auto_staging
from rag.runtime.auto_index_incremental_adapter import import_into_approved_auto_stage
from rag.runtime.auto_index_incremental_verify import verify_isolated_reuse_batch
from rag.runtime.auto_index_batch import inventory_auto_vectors
from rag.index.qdrant_local import open_qdrant_local,close_qdrant_local
from rag.index.vector_ids import deterministic_vector_point_id
from rag.models.code_embedding import CODE_EMBEDDING_DIMENSION


class ApprovedStageImportLabTests(unittest.TestCase):
    def test_approved_queue_binds_synthetic_code_vector_to_own_stage(self):
        with tempfile.TemporaryDirectory(prefix="ragauto05-approved-") as temporary:
            root=Path(temporary)
            sources=root/"source"
            sources.mkdir()
            (sources/"entry.py").write_text("def routine():\n    return 42\n",encoding="utf-8")
            queue=default_queue_path(root)
            project="ragauto05-stage-lab"
            draft=create_draft(queue,project_id=project,source_root=sources,
                               idempotency_key="approved-stage-lab-123456",allow_write=True)
            preview=build_auto_index_preview(project,sources)
            approve_auto_index_draft(queue,draft["job_id"],preview,
                                     confirmed_digest=preview["review_sha256"],
                                     operator_approved=True,allow_write=True)
            stage=Path(prepare_auto_staging(
                queue,draft["job_id"],
                operator_approved=True,preparation_enabled=True)["stage"])
            with closing(sqlite3.connect(
                (stage/"rag_index.sqlite3").as_uri()+"?mode=ro",uri=True,
            )) as connection:
                row=connection.execute(
                    "SELECT chunk_id,path,sha256,source_type,document_id,content FROM rag_chunks LIMIT 1"
                ).fetchone()
            self.assertEqual(row[3],"CODE")
            chunk,path,sha,kind,document_id,content=row
            receipt={
                "mode":"CHUNK_RECEIPT_ONLY","project_id":project,
                "candidate_chunk_ids":{path:[chunk]},
                "candidate_vector_count":1,"vector_copy_authorized":False,
            }
            reviewed={"sources":[{"path":path,"sha256":sha,"index_kind":"CODE"}]}
            point_id=deterministic_vector_point_id(project,"code",chunk)
            records={"TEXT":[],"CODE":[{
                "id":point_id,"vector":[0.01]*CODE_EMBEDDING_DIMENSION,
                "payload":{"project_namespace":project,"chunk_id":chunk,
                           "path":path,"sha256":sha,"source_type":"CODE",
                           "document_id":document_id,"content":content},
            }]}
            token="d"*32
            imported=import_into_approved_auto_stage(
                queue,draft["job_id"],receipt,reviewed,records,
                operator_approved=True,batch_id=token)
            self.assertEqual(imported["vectors_written"],1)
            client=open_qdrant_local(stage/"qdrant")
            try:
                proof=verify_isolated_reuse_batch(client,stage,token,receipt,reviewed)
            finally:
                close_qdrant_local(client)
            self.assertEqual(proof["checked_vectors"],1)
            self.assertTrue(proof["revalidation_passed"])
            inventory=inventory_auto_vectors(queue,draft["job_id"])
            self.assertEqual(inventory["code_done"],1)
            self.assertIn(chunk,inventory["code_ids"])
            self.assertFalse(imported["public_pointer_updated"])
