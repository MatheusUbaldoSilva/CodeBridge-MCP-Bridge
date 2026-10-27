"""RAG-AUTO-05: real approval receipts and source-change integration test."""
from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from rag.runtime.auto_index_queue import create_draft, default_queue_path
from rag.runtime.auto_index_approval import (
    approve_auto_index_draft, build_auto_index_preview,
)
from rag.runtime.auto_index_incremental_review import plan_reviewed_incremental_delta


class ReviewedFilesystemIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/"project"
        self.root.mkdir()
        (self.root/"keep.py").write_text("print('keep')\n",encoding="utf-8")
        (self.root/"change.py").write_text("print('v1')\n",encoding="utf-8")
        self.queue=default_queue_path(Path(self.temp.name))
        self.project="incremental-lab"

    def approve(self,key):
        draft=create_draft(self.queue,project_id=self.project,
            source_root=self.root,idempotency_key=key,allow_write=True)
        preview=build_auto_index_preview(self.project,self.root)
        approve_auto_index_draft(
            self.queue,draft["job_id"],preview,
            confirmed_digest=preview["review_sha256"],
            operator_approved=True,allow_write=True,
        )
        return draft["job_id"],preview

    def plan(self,base,candidate,revision):
        with (
            patch("rag.runtime.auto_index_incremental_review.verify_prepared_auto_generation",
                  return_value={"verified":True,"project_id":self.project,
                                "source_revision":revision}),
            patch("rag.runtime.auto_index_incremental_review.inspect_reusable_manifest_chunks",
                  return_value={"candidate_vector_count":1,"vector_copy_authorized":False}),
        ):
            return plan_reviewed_incremental_delta(
                self.queue,base,candidate,
                baseline_text_model="text-rev",
                candidate_text_model="text-rev",
                baseline_code_model="code-rev",
                candidate_code_model="code-rev",
            )

    def test_changed_source_and_new_file_are_identified(self):
        base,baseline=self.approve("incremental-base-123456789")
        with closing(sqlite3.connect(self.queue)) as cn:
            cn.execute("UPDATE auto_jobs SET state='READY_FOR_REVIEW' WHERE job_id=?",(base,))
            cn.commit()
        (self.root/"change.py").write_text("print('v2')\n",encoding="utf-8")
        (self.root/"new.py").write_text("print('added')\n",encoding="utf-8")
        candidate,_=self.approve("incremental-next-123456789")
        result=self.plan(base,candidate,baseline["review_sha256"])
        self.assertEqual(result["eligible_reuse_sources"],["keep.py"])
        self.assertEqual(result["reindex_sources"],["change.py","new.py"])
        self.assertFalse(result["worker_started"])
        self.assertFalse(result["reuse_authorized"])

    def test_deleted_source_is_removed_without_reindexing_unchanged_file(self):
        base,baseline=self.approve("incremental-base-123456789")
        with closing(sqlite3.connect(self.queue)) as cn:
            cn.execute("UPDATE auto_jobs SET state='READY_FOR_REVIEW' WHERE job_id=?",(base,))
            cn.commit()
        (self.root/"change.py").unlink()
        candidate,_=self.approve("incremental-next-123456789")
        result=self.plan(base,candidate,baseline["review_sha256"])
        self.assertEqual(result["eligible_reuse_sources"],["keep.py"])
        self.assertEqual(result["removed_sources"],["change.py"])
        self.assertEqual(result["reindex_sources"],[])
        self.assertFalse(result["public_pointer_updated"])

    def test_candidate_modified_after_approval_is_rejected(self):
        base,baseline=self.approve("incremental-base-123456789")
        with closing(sqlite3.connect(self.queue)) as cn:
            cn.execute("UPDATE auto_jobs SET state='READY_FOR_REVIEW' WHERE job_id=?",(base,))
            cn.commit()
        candidate,_=self.approve("incremental-next-123456789")
        (self.root/"change.py").write_text("print('tampered')\n",encoding="utf-8")
        with self.assertRaises(ValueError):
            self.plan(base,candidate,baseline["review_sha256"])
