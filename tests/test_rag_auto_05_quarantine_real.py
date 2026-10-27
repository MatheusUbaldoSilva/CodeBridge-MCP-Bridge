"""RAG-AUTO-05-F real SQLite queue + non-destructive interrupted stage quarantine."""
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from rag.runtime.auto_index_queue import create_draft, default_queue_path
from rag.runtime.auto_index_approval import approve_auto_index_draft, build_auto_index_preview
from rag.runtime.auto_index_staging import prepare_auto_staging
from rag.runtime.auto_index_incremental_quarantine import quarantine_interrupted_incremental_stage


class RealInterruptedStageQuarantineTests(unittest.TestCase):
    def test_approved_paused_job_stage_moves_without_deletion(self):
        with tempfile.TemporaryDirectory(prefix="ragauto05-recovery-real-") as tmp:
            base=Path(tmp)
            source=base/"sources"
            source.mkdir()
            (source/"mod.py").write_text("def value(): return 2\n",encoding="utf-8")
            queue=default_queue_path(base)
            draft=create_draft(queue,project_id="rollback-real-lab",
                source_root=source,idempotency_key="rollback-real-lab-1234567",
                allow_write=True)
            preview=build_auto_index_preview("rollback-real-lab",source)
            approve_auto_index_draft(queue,draft["job_id"],preview,
                confirmed_digest=preview["review_sha256"],
                operator_approved=True,allow_write=True)
            original=Path(prepare_auto_staging(
                queue,draft["job_id"],operator_approved=True,
                preparation_enabled=True)["stage"])
            evidence=original/"rag_index.sqlite3"
            original_size=evidence.stat().st_size
            with closing(sqlite3.connect(queue)) as connection:
                connection.execute("UPDATE auto_jobs SET state='PAUSED' WHERE job_id=?",
                                   (draft["job_id"],))
                connection.commit()
            result=quarantine_interrupted_incremental_stage(
                queue,draft["job_id"],operator_approved=True,
                confirmation="RAG_AUTO_QUARANTINE:"+draft["job_id"])
            quarantined=Path(result["quarantine_path"])
            self.assertFalse(original.exists())
            self.assertTrue(quarantined.is_dir())
            self.assertEqual((quarantined/"rag_index.sqlite3").stat().st_size,original_size)
            self.assertTrue((quarantined/"qdrant").is_dir())
            self.assertFalse(result["vectors_deleted"])
            self.assertFalse(result["public_pointer_updated"])
