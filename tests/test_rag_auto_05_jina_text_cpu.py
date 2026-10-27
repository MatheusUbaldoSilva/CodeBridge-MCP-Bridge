"""Opt-in RAG-AUTO-05 TEXT CPU canary; skips on low memory.

Only isolated temporary stages. Never executes in ordinary test regression.
"""
import os
from pathlib import Path
import tempfile
import unittest

from rag.runtime.auto_index_worker import _free_ram_mib
from rag.runtime.auto_index_queue import create_draft, default_queue_path
from rag.runtime.auto_index_approval import approve_auto_index_draft, build_auto_index_preview
from rag.runtime.auto_index_staging import prepare_auto_staging
from rag.runtime.auto_index_batch import inventory_auto_vectors, _COLUMNS
from rag.runtime.production_index import _write_vectors
from rag.runtime.auto_index_incremental_read import read_reusable_vectors
from rag.runtime.auto_index_incremental_adapter import import_into_approved_auto_stage
from rag.index.qdrant_local import open_qdrant_local, close_qdrant_local
from contextlib import closing
import sqlite3


@unittest.skipUnless(os.environ.get("RAG_AUTO05_TEXT_CPU")=="1",
                     "TEXT CPU Jina canary is explicit opt-in")
class TextCpuCanary(unittest.TestCase):
    def test_reuse_actual_text_cpu_vector_without_reembedding(self):
        if _free_ram_mib() < 3000:
            self.skipTest("free RAM under safe 3000 MiB TEXT CPU threshold")
        with tempfile.TemporaryDirectory(prefix="auto05-text-cpu-") as tmp:
            base=Path(tmp)
            src=base/"approved-source"
            src.mkdir()
            (src/"guide.md").write_text("# Documentation\nA short RAG canary.\n",encoding="utf-8")
            queue=default_queue_path(base)
            project="auto05-text-cpu-lab"
            items=[]
            for number in (1,2):
                draft=create_draft(queue,project_id=project,source_root=src,
                    idempotency_key=f"text-cpu-canary-{number}-1234567",
                    allow_write=True)
                preview=build_auto_index_preview(project,src)
                approve_auto_index_draft(queue,draft["job_id"],preview,
                    confirmed_digest=preview["review_sha256"],
                    operator_approved=True,allow_write=True)
                prepared=prepare_auto_staging(queue,draft["job_id"],
                    operator_approved=True,preparation_enabled=True)
                items.append((draft["job_id"],Path(prepared["stage"])))
            (first_id,first),(second_id,second)=items
            with closing(sqlite3.connect(
                (first/"rag_index.sqlite3").as_uri()+"?mode=ro",uri=True)) as cn:
                rows=cn.execute(f"SELECT {_COLUMNS} FROM rag_chunks ORDER BY chunk_id").fetchall()
            self.assertTrue(rows)
            self.assertTrue(all(row[3]!="CODE" for row in rows))
            _write_vectors(first/"qdrant",project,rows,[],text_cpu_only=True)
            original=inventory_auto_vectors(queue,first_id)
            self.assertTrue(original["complete"])
            receipt={"mode":"CHUNK_RECEIPT_ONLY","project_id":project,
                "candidate_chunk_ids":{"guide.md":[row[0] for row in rows]},
                "candidate_vector_count":len(rows),"vector_copy_authorized":False}
            approved={"sources":[{"path":"guide.md",
                "sha256":rows[0][7],"index_kind":"TEXT"}]}
            client=open_qdrant_local(first/"qdrant")
            try:
                vectors=read_reusable_vectors(client,receipt,approved)
            finally:
                close_qdrant_local(client)
            transferred=import_into_approved_auto_stage(
                queue,second_id,receipt,approved,vectors,
                operator_approved=True,batch_id="f"*32)
            self.assertEqual(transferred["vectors_written"],len(rows))
            candidate=inventory_auto_vectors(queue,second_id)
            self.assertTrue(candidate["complete"])
            self.assertEqual(original["text_ids"],candidate["text_ids"])
            self.assertFalse(transferred["public_pointer_updated"])
