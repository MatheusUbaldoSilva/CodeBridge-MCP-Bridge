"""RAG-AUTO-05-E recovery inspection tests."""
from pathlib import Path
import tempfile
import unittest

from rag.runtime.auto_index_incremental_recovery import inspect_incremental_stage_recovery
from rag.runtime.auto_index_incremental_checkpoint import persist_isolated_batch_receipt


class StageRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.stage=Path(self.tmp.name)
        self.batch="e"*32
        self.write={"mode":"ISOLATED_STAGE_BATCH_WRITTEN",
                    "vectors_written":1,"public_pointer_updated":False,
                    "requires_staging_revalidation":True}

    def state(self):
        return inspect_incremental_stage_recovery(self.stage,self.batch)

    def test_new_stage_has_no_auto_actions(self):
        self.assertEqual(self.state()["state"],"NOT_STARTED")
        self.assertFalse(self.state()["safe_to_auto_retry"])

    def test_stale_lock_requires_manual_audit(self):
        (self.stage/".ragauto05-active-batch.lock").write_text("stale")
        result=self.state()
        self.assertEqual(result["state"],"POSSIBLY_UNCHECKPOINTED_VECTORS")
        self.assertTrue(result["requires_manual_audit"])
        self.assertFalse(result["safe_to_auto_retry"])

    def test_valid_receipt_requires_qdrant_readback(self):
        persist_isolated_batch_receipt(self.stage,self.batch,self.write,allow_write=True)
        state=self.state()
        self.assertEqual(state["state"],"CHECKPOINT_AWAITING_QDRANT")
        self.assertFalse(state["safe_to_auto_retry"])
        self.assertTrue(state["requires_manual_audit"])
        (self.stage/".ragauto05-active-batch.lock").write_text("stale")
        self.assertEqual(self.state()["state"],"CHECKPOINT_PRESENT_LOCKED")

    def test_incomplete_temp_detected(self):
        (self.stage/("batch_"+self.batch+".writing")).write_text("partial")
        self.assertEqual(self.state()["state"],"INTERRUPTED_RECEIPT")

    def test_redirected_receipt_requires_audit_when_symlinks_available(self):
        source=self.stage/"external"
        source.write_text("{}")
        target=self.stage/("batch_"+self.batch+".json")
        try:
            target.symlink_to(source)
        except (OSError,NotImplementedError):
            self.skipTest("symlink creation unavailable on Windows")
        result=self.state()
        self.assertEqual(result["state"],"REDIRECTED_RECOVERY_ARTIFACT")
        self.assertTrue(result["redirected_artifact_present"])
        self.assertTrue(result["requires_manual_audit"])
        self.assertFalse(result["safe_to_auto_retry"])

    def test_corrupted_receipt_detected(self):
        (self.stage/("batch_"+self.batch+".json")).write_text("{}")
        self.assertEqual(self.state()["state"],"INVALID_CHECKPOINT")
