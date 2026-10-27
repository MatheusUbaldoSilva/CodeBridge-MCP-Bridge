"""RAG-AUTO-05-F supervised runner authorization and release tests."""
import unittest
from pathlib import Path
from rag.models.backend_policy import TEXT_MODEL_REVISION
from rag.models.code_backend_policy import CODE_MODEL_REVISION
from unittest.mock import patch

from rag.runtime.auto_index_incremental_supervised import run_supervised_incremental_batch

M="rag.runtime.auto_index_incremental_supervised."

class SupervisedIncrementalTests(unittest.TestCase):
    def setUp(self):
        self.args=dict(queue_path=Path("canary-queue"),baseline_job_id="a"*32,
            candidate_job_id="b"*32,execute=True,operator_approved=True,
            confirmation="RAG_AUTO_INCREMENTAL_RUN:"+"b"*32,
            baseline_text_model=TEXT_MODEL_REVISION,candidate_text_model=TEXT_MODEL_REVISION,
            baseline_code_model=CODE_MODEL_REVISION,candidate_code_model=CODE_MODEL_REVISION)
        self.lease={"state":"RESERVED_NO_WORKER","lease_token":"f"*32,
                    "generation":4}
    def test_succeeds_only_after_staging_and_exact_release(self):
        with (
            patch(M+"_free_ram_mib",return_value=4096),
            patch(M+"inventory_auto_vectors",return_value={"complete":False}),
            patch(M+"_begin_batch"),
            patch(M+"update_auto_checkpoint",return_value={"state":"QUEUED"}),
            patch(M+"_public_generation",return_value="unchanged-generation") as pointer,
            patch(M+"reserve_index_supervisor",return_value=self.lease) as reserve,
            patch(M+"prepare_auto_staging") as stage,
            patch(M+"execute_fenced_incremental_batch",
                  return_value={"vectors_written":2}) as worker,
            patch(M+"release_index_supervisor",return_value={"accepted":True}) as release,
        ):
            result=run_supervised_incremental_batch(**self.args)
        self.assertFalse(result["public_pointer_updated"])
        self.assertEqual(result["public_generation_unchanged"],"unchanged-generation")
        self.assertEqual(pointer.call_count,3)
        stage.assert_called_once()
        worker.assert_called_once()
        self.assertEqual(worker.call_args.kwargs["lease_token"],"f"*32)
        release.assert_called_once_with(
            self.args["queue_path"],self.args["candidate_job_id"],"f"*32,4)

    def test_low_memory_refuses_staging_and_worker(self):
        with (
            patch(M+"_free_ram_mib",return_value=1100),
            patch(M+"reserve_index_supervisor") as reserve,
            patch(M+"prepare_auto_staging") as staging,
        ):
            value=run_supervised_incremental_batch(**self.args)
        self.assertEqual(value["state"],"WAITING_FOR_MEMORY")
        self.assertFalse(value["worker_started"])
        reserve.assert_not_called()
        staging.assert_not_called()

    def test_batch_index_forwarded_to_fenced_worker(self):
        with (
            patch(M+"_free_ram_mib",return_value=4096),
            patch(M+"_public_generation",return_value="generation"),
            patch(M+"reserve_index_supervisor",return_value=self.lease),
            patch(M+"prepare_auto_staging"),
            patch(M+"execute_fenced_incremental_batch",
                  return_value={"vectors_written":1}) as worker,
            patch(M+"inventory_auto_vectors",return_value={"complete":False}),
            patch(M+"_begin_batch"),
            patch(M+"update_auto_checkpoint",return_value={"state":"QUEUED"}),
            patch(M+"release_index_supervisor",return_value={"accepted":True}),
        ):
            value=run_supervised_incremental_batch(**self.args,batch_index=3)
        self.assertEqual(value["state"],"QUEUED")
        self.assertEqual(worker.call_args.kwargs["batch_index"],3)

    def test_invalid_batch_index_denied_before_reservation(self):
        with patch(M+"reserve_index_supervisor") as reserved:
            for index in (-1,True,1.5,"0"):
                with self.subTest(index=index),self.assertRaises(ValueError):
                    run_supervised_incremental_batch(**self.args,batch_index=index)
            reserved.assert_not_called()

    def test_unpinned_model_revision_never_reserves_worker(self):
        with patch(M+"reserve_index_supervisor") as reserved:
            with self.assertRaisesRegex(PermissionError,"pinned models"):
                run_supervised_incremental_batch(
                    **{**self.args,"candidate_code_model":"user-supplied-model"})
            reserved.assert_not_called()

    def test_denies_without_exact_job_confirmation(self):
        with patch(M+"reserve_index_supervisor") as reserved:
            for update in ({"execute":False},
                           {"operator_approved":False},
                           {"confirmation":"RAG_AUTO_RUN:"+"b"*32}):
                with self.assertRaises(PermissionError):
                    run_supervised_incremental_batch(**{**self.args,**update})
            reserved.assert_not_called()

    def test_busy_does_not_stage_or_release(self):
        with (
            patch(M+"_free_ram_mib",return_value=4096),
            patch(M+"inventory_auto_vectors",return_value={"complete":False}),
            patch(M+"_begin_batch"),
            patch(M+"update_auto_checkpoint",return_value={"state":"QUEUED"}),
            patch(M+"_public_generation",return_value="generation"),
            patch(M+"reserve_index_supervisor",return_value={
                "state":"SUPERVISOR_BUSY"}) as reservation,
            patch(M+"prepare_auto_staging") as stage,
            patch(M+"release_index_supervisor") as release,
        ):
            value=run_supervised_incremental_batch(**self.args)
        self.assertEqual(value["state"],"SUPERVISOR_BUSY")
        stage.assert_not_called()
        release.assert_not_called()

    def test_failure_preserves_fenced_release(self):
        with (
            patch(M+"_free_ram_mib",return_value=4096),
            patch(M+"inventory_auto_vectors",return_value={"complete":False}),
            patch(M+"_begin_batch"),
            patch(M+"update_auto_checkpoint",return_value={"state":"QUEUED"}),
            patch(M+"_public_generation",return_value="generation"),
            patch(M+"reserve_index_supervisor",return_value=self.lease),
            patch(M+"prepare_auto_staging",side_effect=RuntimeError("stage")) ,
            patch(M+"release_index_supervisor") as released,
            self.assertRaisesRegex(RuntimeError,"stage"),
        ):
            run_supervised_incremental_batch(**self.args)
        released.assert_called_once()

    def test_checkpoint_failure_requests_paused_state_and_releases(self):
        with (
            patch(M+"_free_ram_mib",return_value=4096),
            patch(M+"_public_generation",return_value="generation"),
            patch(M+"reserve_index_supervisor",return_value=self.lease),
            patch(M+"prepare_auto_staging"),
            patch(M+"execute_fenced_incremental_batch",
                  return_value={"vectors_written":1}),
            patch(M+"inventory_auto_vectors",return_value={"complete":False}),
            patch(M+"_begin_batch"),
            patch(M+"update_auto_checkpoint",
                  side_effect=[OSError("disk full"),{"state":"PAUSED"}]) as checkpoints,
            patch(M+"release_index_supervisor",
                  return_value={"accepted":True}) as released,
            self.assertRaisesRegex(OSError,"disk full"),
        ):
            run_supervised_incremental_batch(**self.args)
        self.assertEqual(checkpoints.call_count,2)
        self.assertEqual(checkpoints.call_args.kwargs["failure"],"OSError")
        released.assert_called_once()

    def test_rejected_release_never_reports_success(self):
        with (
            patch(M+"_free_ram_mib",return_value=4096),
            patch(M+"inventory_auto_vectors",return_value={"complete":False}),
            patch(M+"_begin_batch"),
            patch(M+"update_auto_checkpoint",return_value={"state":"QUEUED"}),
            patch(M+"_public_generation",return_value="generation"),
            patch(M+"reserve_index_supervisor",return_value=self.lease),
            patch(M+"prepare_auto_staging"),
            patch(M+"execute_fenced_incremental_batch",
                  return_value={"vectors_written":1}),
            patch(M+"release_index_supervisor",
                  return_value={"accepted":False}),
            self.assertRaisesRegex(RuntimeError,"release not confirmed"),
        ):
            run_supervised_incremental_batch(**self.args)

    def test_public_pointer_drift_blocks_transfer(self):
        with (
            patch(M+"_free_ram_mib",return_value=4096),
            patch(M+"inventory_auto_vectors",return_value={"complete":False}),
            patch(M+"_begin_batch"),
            patch(M+"update_auto_checkpoint",return_value={"state":"QUEUED"}),
            patch(M+"_public_generation",side_effect=["first","other"]),
            patch(M+"reserve_index_supervisor",return_value=self.lease),
            patch(M+"prepare_auto_staging"),
            patch(M+"execute_fenced_incremental_batch") as worker,
            patch(M+"release_index_supervisor") as released,
            self.assertRaisesRegex(RuntimeError,"public generation changed"),
        ):
            run_supervised_incremental_batch(**self.args)
        worker.assert_not_called()
        released.assert_called_once()
