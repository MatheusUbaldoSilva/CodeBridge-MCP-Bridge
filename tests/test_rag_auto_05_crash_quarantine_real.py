"""RAG-AUTO-05-F: real partially-written Qdrant batch quarantined without deletion."""
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from rag.runtime.auto_index_queue import create_draft, default_queue_path
from rag.runtime.auto_index_approval import build_auto_index_preview, approve_auto_index_draft
from rag.runtime.auto_index_staging import prepare_auto_staging
from rag.runtime.auto_index_incremental_adapter import import_into_approved_auto_stage
from rag.runtime.auto_index_incremental_quarantine import quarantine_interrupted_incremental_stage
from rag.index.qdrant_local import open_qdrant_local,close_qdrant_local
from rag.index.vector_ids import deterministic_vector_point_id
from rag.models.code_embedding import CODE_EMBEDDING_DIMENSION


class RealCrashQuarantineTests(unittest.TestCase):
    def test_checkpoint_disk_failure_preserves_partial_qdrant_in_quarantine(self):
        with tempfile.TemporaryDirectory(prefix="auto05-crash-proof-") as tmp:
            home=Path(tmp)
            source=home/"src"
            source.mkdir()
            (source/"program.py").write_text("def safe():\n    return 5\n",encoding="utf-8")
            queue=default_queue_path(home)
            project="crash-proof-canary"
            draft=create_draft(queue,project_id=project,source_root=source,
                idempotency_key="crash-proof-stage-12345",allow_write=True)
            preview=build_auto_index_preview(project,source)
            approve_auto_index_draft(queue,draft["job_id"],preview,
                confirmed_digest=preview["review_sha256"],
                operator_approved=True,allow_write=True)
            stage=Path(prepare_auto_staging(
                queue,draft["job_id"],operator_approved=True,
                preparation_enabled=True)["stage"])
            with closing(sqlite3.connect(
                (stage/"rag_index.sqlite3").as_uri()+"?mode=ro",uri=True,
            )) as cn:
                chunk,doc,content,kind,path,sha=cn.execute(
                    "SELECT chunk_id,document_id,content,source_type,path,sha256 "
                    "FROM rag_chunks LIMIT 1"
                ).fetchone()
            self.assertEqual(kind,"CODE")
            uid=deterministic_vector_point_id(project,"code",chunk)
            receipt={"mode":"CHUNK_RECEIPT_ONLY","project_id":project,
                "candidate_chunk_ids":{path:[chunk]},
                "candidate_vector_count":1,"vector_copy_authorized":False}
            source_receipt={"sources":[{"path":path,"sha256":sha,"index_kind":"CODE"}]}
            records={"TEXT":[],"CODE":[{
                "id":uid,"vector":[0.1]*CODE_EMBEDDING_DIMENSION,
                "payload":{"project_namespace":project,"chunk_id":chunk,
                           "document_id":doc,"content":content,"source_type":kind,
                           "path":path,"sha256":sha},
            }]}
            with (
                patch("rag.runtime.auto_index_incremental_execute.persist_isolated_batch_receipt",
                      side_effect=OSError("simulated disk-full")),
                self.assertRaisesRegex(RuntimeError,"incomplete vectors"),
            ):
                import_into_approved_auto_stage(
                    queue,draft["job_id"],receipt,source_receipt,records,
                    operator_approved=True,batch_id="d"*32)
            self.assertTrue((stage/".ragauto05-active-batch.lock").is_file())
            self.assertFalse((stage/("batch_"+"d"*32+".json")).exists())
            with closing(sqlite3.connect(queue)) as cn:
                cn.execute("UPDATE auto_jobs SET state='PAUSED' WHERE job_id=?",
                           (draft["job_id"],))
                cn.commit()
            quarantined=quarantine_interrupted_incremental_stage(
                queue,draft["job_id"],operator_approved=True,
                confirmation="RAG_AUTO_QUARANTINE:"+draft["job_id"])
            saved=Path(quarantined["quarantine_path"])
            self.assertTrue((saved/".ragauto05-active-batch.lock").is_file())
            client=open_qdrant_local(saved/"qdrant")
            try:
                values=client.retrieve(collection_name="code",ids=[uid],
                                       with_payload=True,with_vectors=False)
                self.assertEqual(len(values),1)
                self.assertEqual(values[0].payload["sha256"],sha)
            finally:
                close_qdrant_local(client)
            self.assertFalse(quarantined["public_pointer_updated"])
