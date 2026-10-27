"""RAG-AUTO-05-E isolated executor checkpoint and failure tests."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from rag.runtime.auto_index_incremental_execute import execute_isolated_reuse_batch
from rag.runtime.auto_index_incremental_checkpoint import read_isolated_batch_receipt


class IsolatedExecuteTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.stage=Path(self.tmp.name)
        self.destination=Mock()
        self.token="c"*32
        self.write={"mode":"ISOLATED_STAGE_BATCH_WRITTEN","vectors_written":2,
                    "requires_staging_revalidation":True,
                    "public_pointer_updated":False}

    def execute(self):
        return execute_isolated_reuse_batch(
            self.destination,self.stage,{}, {},{},
            approve_isolated_stage=True,batch_id=self.token,
        )

    def test_writes_checkpoint_after_import_only(self):
        with patch("rag.runtime.auto_index_incremental_execute.import_verified_reuse_batch",
                   return_value=self.write) as importer:
            result=self.execute()
        self.assertEqual(result["recovery_state"],"REVALIDATE_BEFORE_RESUME")
        self.assertFalse(result["generation_activated"])
        self.assertEqual(read_isolated_batch_receipt(self.stage,self.token)["vectors_written"],2)
        importer.assert_called_once()
        self.assertFalse((self.stage/".ragauto05-active-batch.lock").exists())

    def test_invalid_authorization_refuses_write(self):
        with patch("rag.runtime.auto_index_incremental_execute.import_verified_reuse_batch") as writer:
            with self.assertRaises(PermissionError):
                execute_isolated_reuse_batch(self.destination,self.stage,{},{},{})
            writer.assert_not_called()

    def test_checkpoint_failure_does_not_claim_success(self):
        with (
            patch("rag.runtime.auto_index_incremental_execute.import_verified_reuse_batch",
                  return_value=self.write),
            patch("rag.runtime.auto_index_incremental_execute.persist_isolated_batch_receipt",
                  side_effect=OSError("disk full")),
        ):
            with self.assertRaisesRegex(RuntimeError,"incomplete vectors"):
                self.execute()
        self.assertFalse((self.stage/("batch_"+self.token+".json")).exists())
        self.assertTrue((self.stage/".ragauto05-active-batch.lock").exists())

    def test_stale_lock_blocks_retry_even_with_new_batch_id(self):
        (self.stage/".ragauto05-active-batch.lock").write_text("old-batch")
        with patch(
            "rag.runtime.auto_index_incremental_execute.import_verified_reuse_batch"
        ) as importer:
            with self.assertRaises(FileExistsError):
                self.execute()
            importer.assert_not_called()

    def test_existing_receipt_refuses_replay(self):
        with patch("rag.runtime.auto_index_incremental_execute.import_verified_reuse_batch",
                   return_value=self.write) as importer:
            self.execute()
            with self.assertRaises(ValueError):
                self.execute()
            importer.assert_called_once()
        self.assertFalse((self.stage/".ragauto05-active-batch.lock").exists())
