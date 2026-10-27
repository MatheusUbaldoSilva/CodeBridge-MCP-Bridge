"""RAG-AUTO-05-F non-destructive quarantine tests."""
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from rag.runtime.auto_index_incremental_quarantine import quarantine_interrupted_incremental_stage

M="rag.runtime.auto_index_incremental_quarantine."

class QuarantineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.stage=Path(self.tmp.name)/("job-"+"a"*32)
        self.stage.mkdir()
        (self.stage/"keep-vector.txt").write_text("never delete data",encoding="utf-8")
        self.job={"approved":True,"state":"PAUSED","project_id":"private-lab"}
        self.args=dict(queue_path=Path("unused"),job_id="a"*32,
                       operator_approved=True,
                       confirmation="RAG_AUTO_QUARANTINE:"+"a"*32)
    def context(self,lease=None,job=None):
        from contextlib import ExitStack
        stack=ExitStack()
        stack.enter_context(patch(M+"get_job",return_value=self.job if job is None else job))
        stack.enter_context(patch(M+"stage_directory",return_value=self.stage))
        stack.enter_context(patch(M+"inspect_index_supervisor",
                                  return_value={"state":"NOT_RESERVED"} if lease is None else lease))
        return stack
    def test_quarantine_is_atomic_and_non_destructive(self):
        with self.context():
            result=quarantine_interrupted_incremental_stage(**self.args)
        moved=Path(result["quarantine_path"])
        self.assertTrue(moved.is_dir())
        self.assertEqual((moved/"keep-vector.txt").read_text(encoding="utf-8"),"never delete data")
        self.assertFalse(self.stage.exists())
        self.assertFalse(result["vectors_deleted"])
        self.assertFalse(result["public_pointer_updated"])
    def test_refuses_live_lease_without_moving(self):
        lease={"state":"LEASE_RECORDED","lease_until_epoch":time.time()+100}
        with self.context(lease),self.assertRaises(PermissionError):
            quarantine_interrupted_incremental_stage(**self.args)
        self.assertTrue(self.stage.exists())
    def test_expired_or_unknown_lease_fails_closed(self):
        cases = (
            {"state":"LEASE_RECORDED","lease_until_epoch":time.time()-500},
            {"state":"LEASE_RECORDED"},
            {"state":"UNAVAILABLE"},
            {},
        )
        for lease in cases:
            with self.subTest(lease=lease):
                with self.context(lease=lease),self.assertRaises(PermissionError):
                    quarantine_interrupted_incremental_stage(**self.args)
                self.assertTrue(self.stage.exists())
    def test_missing_confirmation_or_running_job_denied(self):
        with self.context(),self.assertRaises(PermissionError):
            quarantine_interrupted_incremental_stage(
                **{**self.args,"confirmation":""})
        with self.context(job={**self.job,"state":"RUNNING"}),self.assertRaises(PermissionError):
            quarantine_interrupted_incremental_stage(**self.args)
        self.assertTrue(self.stage.exists())
    def test_new_supervisor_reservation_before_rename_refuses_move(self):
        from contextlib import nullcontext
        with (
            patch(M+"get_job",return_value=self.job),
            patch(M+"stage_directory",return_value=self.stage),
            patch(M+"production_generation_lock",return_value=nullcontext()) as lock,
            patch(M+"inspect_index_supervisor",side_effect=[
                {"state":"NOT_RESERVED"},
                {"state":"LEASE_RECORDED","lease_until_epoch":time.time()+100},
            ]),
            self.assertRaisesRegex(PermissionError,"became reserved"),
        ):
            quarantine_interrupted_incremental_stage(**self.args)
        lock.assert_called_once_with(exclusive=True,channel="semantic")
        self.assertTrue(self.stage.exists())

    def test_job_turns_running_while_semantic_lock_held(self):
        from contextlib import nullcontext
        with (
            patch(M+"get_job",side_effect=[
                self.job,{**self.job,"state":"RUNNING"},
            ]),
            patch(M+"stage_directory",return_value=self.stage),
            patch(M+"production_generation_lock",return_value=nullcontext()),
            patch(M+"inspect_index_supervisor",return_value={"state":"NOT_RESERVED"}),
            self.assertRaisesRegex(PermissionError,"job changed"),
        ):
            quarantine_interrupted_incremental_stage(**self.args)
        self.assertTrue(self.stage.exists())

    def test_public_project_denied(self):
        with self.context(job={**self.job,"project_id":"codebridge"}),self.assertRaises(PermissionError):
            quarantine_interrupted_incremental_stage(**self.args)
        self.assertTrue(self.stage.exists())
