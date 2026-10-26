"""RAG-AUTO-02 recovery tests for fenced crashed-job reconciliation."""
from contextlib import nullcontext,closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from rag.runtime.auto_index_queue import create_draft,default_queue_path,get_job,AutoIndexQueueError
from rag.runtime.auto_index_approval import build_auto_index_preview,approve_auto_index_draft
from rag.runtime.auto_index_staging import prepare_auto_staging
from rag.runtime.auto_index_supervisor import reserve_index_supervisor
from rag.runtime.auto_index_checkpoint import recover_orphaned_auto_job,update_auto_checkpoint


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base=Path(temp.name)
        self.source=self.base/"code"
        self.source.mkdir()
        (self.source/"README.md").write_text("RAG recovery\n",encoding="utf-8")
        self.db=default_queue_path(self.base)
        draft=create_draft(
            self.db,project_id="recovery-test",source_root=self.source,
            idempotency_key="recovery-123456789",allow_write=True,
        )
        self.job=draft["job_id"]
        preview=build_auto_index_preview("recovery-test",self.source)
        approve_auto_index_draft(
            self.db,self.job,preview,
            confirmed_digest=preview["review_sha256"],
            operator_approved=True,allow_write=True,
        )
        prepare_auto_staging(
            self.db,self.job,operator_approved=True,preparation_enabled=True,
        )
        self.owner=reserve_index_supervisor(
            self.db,self.job,reservation_enabled=True,operator_approved=True,
            lease_seconds=30,now_epoch=100,
        )
        with closing(sqlite3.connect(self.db)) as cn:
            cn.execute("UPDATE auto_jobs SET state='RUNNING' WHERE job_id=?",(self.job,))
            cn.commit()

    def test_cannot_recover_before_lease_expires(self):
        with self.assertRaises(AutoIndexQueueError):
            recover_orphaned_auto_job(
                self.db,self.job,operator_approved=True,now_epoch=129,
                semantic_guard_factory=nullcontext,
            )
        self.assertEqual(get_job(self.db,self.job)["state"],"RUNNING")

    def test_expired_worker_reconciles_without_reembedding(self):
        answer=recover_orphaned_auto_job(
            self.db,self.job,operator_approved=True,now_epoch=131,
            semantic_guard_factory=nullcontext,
        )
        self.assertEqual(answer["state"],"QUEUED")
        self.assertEqual(answer["vectors_done"],0)
        self.assertEqual(get_job(self.db,self.job)["state"],"QUEUED")
        with self.assertRaises(AutoIndexQueueError):
            update_auto_checkpoint(
                self.db,self.job,self.owner["lease_token"],
                self.owner["generation"],now_epoch=132,
            )

    def test_recovery_requires_operator_confirmation(self):
        with self.assertRaises(PermissionError):
            recover_orphaned_auto_job(
                self.db,self.job,semantic_guard_factory=nullcontext,now_epoch=200,
            )

    def test_source_edit_refuses_crash_recovery(self):
        (self.source/"README.md").write_text("secret source changed\n",encoding="utf-8")
        with self.assertRaises(ValueError):
            recover_orphaned_auto_job(
                self.db,self.job,operator_approved=True,now_epoch=200,
                semantic_guard_factory=nullcontext,
            )
        self.assertEqual(get_job(self.db,self.job)["state"],"RUNNING")


if __name__=="__main__":
    unittest.main()
