"""RAG-AUTO-05-F fencing contract tests."""
from pathlib import Path
from contextlib import nullcontext
import unittest
from unittest.mock import patch

from rag.runtime.auto_index_incremental_fenced import execute_fenced_incremental_batch


class FencedIncrementalTests(unittest.TestCase):
    def setUp(self):
        self.kwargs=dict(
            queue_path=Path("unused"),baseline_job_id="a"*32,
            candidate_job_id="b"*32, lease_token="c"*32,
            generation=3,operator_approved=True,
            baseline_text_model="text",candidate_text_model="text",
            baseline_code_model="code",candidate_code_model="code",
        )

    def test_exact_owner_renewed_before_and_after_stage_copy(self):
        with (
            patch("rag.runtime.auto_index_incremental_fenced.renew_index_supervisor",
                  side_effect=[{"accepted":True},{"accepted":True}]) as renewed,
            patch("rag.runtime.auto_index_incremental_fenced.production_generation_lock",return_value=nullcontext()),
            patch("rag.runtime.auto_index_incremental_fenced.transfer_verified_incremental_batch",
                  return_value={"vectors_written":2,"public_pointer_updated":False}) as copied,
        ):
            result=execute_fenced_incremental_batch(**self.kwargs)
        self.assertEqual(renewed.call_count,2)
        copied.assert_called_once()
        self.assertTrue(result["supervisor_fence_rechecked"])
        self.assertTrue(result["stage_revalidation_required"])

    def test_refuses_missing_approval_or_invalid_owner(self):
        for changed in (
            {"operator_approved":False},{"lease_token":""},{"generation":0},
        ):
            with self.subTest(changed=changed), patch(
                "rag.runtime.auto_index_incremental_fenced.transfer_verified_incremental_batch"
            ) as copy, self.assertRaises(PermissionError):
                execute_fenced_incremental_batch(**{**self.kwargs,**changed})
                copy.assert_not_called()

    def test_refuses_foreign_supervisor_before_copy(self):
        with (
            patch("rag.runtime.auto_index_incremental_fenced.renew_index_supervisor",
                  return_value={"accepted":False}),
            patch("rag.runtime.auto_index_incremental_fenced.transfer_verified_incremental_batch") as copy,
            self.assertRaises(PermissionError),
        ):
            execute_fenced_incremental_batch(**self.kwargs)
            copy.assert_not_called()

    def test_fenced_batch_index_passed_through(self):
        with (
            patch("rag.runtime.auto_index_incremental_fenced.renew_index_supervisor",
                  return_value={"accepted":True}),
            patch("rag.runtime.auto_index_incremental_fenced.production_generation_lock",
                  return_value=nullcontext()),
            patch("rag.runtime.auto_index_incremental_fenced.transfer_verified_incremental_batch",
                  return_value={"vectors_written":1}) as transfer,
        ):
            execute_fenced_incremental_batch(**self.kwargs,batch_index=2)
        self.assertEqual(transfer.call_args.kwargs["batch_index"],2)

    def test_semantic_lock_is_acquired_for_incremental_transfer(self):
        from contextlib import nullcontext
        with (
            patch("rag.runtime.auto_index_incremental_fenced.renew_index_supervisor",
                  return_value={"accepted":True}),
            patch("rag.runtime.auto_index_incremental_fenced.production_generation_lock",
                  return_value=nullcontext()) as guard,
            patch("rag.runtime.auto_index_incremental_fenced.transfer_verified_incremental_batch",
                  return_value={"vectors_written":1}),
        ):
            execute_fenced_incremental_batch(**self.kwargs)
        guard.assert_called_once_with(exclusive=True,channel="semantic")

    def test_periodic_heartbeat_renews_during_slow_transfer(self):
        import threading
        started=threading.Event()
        release=threading.Event()
        calls=[]
        def renew(*args,**kwargs):
            calls.append(1)
            if len(calls)>=3:
                release.set()
            return {"accepted":True}
        def slow_transfer(*args,**kwargs):
            started.set()
            self.assertTrue(release.wait(timeout=3))
            return {"vectors_written":1,"public_pointer_updated":False}
        with (
            patch("rag.runtime.auto_index_incremental_fenced.renew_index_supervisor",
                  side_effect=renew),
            patch("rag.runtime.auto_index_incremental_fenced.production_generation_lock",
                  return_value=nullcontext()),
            patch("rag.runtime.auto_index_incremental_fenced.transfer_verified_incremental_batch",
                  side_effect=slow_transfer),
        ):
            result=execute_fenced_incremental_batch(
                **self.kwargs,heartbeat_seconds=1)
        self.assertTrue(started.is_set())
        self.assertGreaterEqual(len(calls),3)
        self.assertTrue(result["supervisor_fence_rechecked"])

    def test_lost_heartbeat_during_transfer_cannot_report_success(self):
        import threading
        heartbeat_lost=threading.Event()
        hits=[]
        def renew(*args,**kwargs):
            hits.append(1)
            if len(hits)==2:
                heartbeat_lost.set()
                return {"accepted":False}
            return {"accepted":True}
        def slow(*args,**kwargs):
            self.assertTrue(heartbeat_lost.wait(timeout=3))
            return {"vectors_written":1,"public_pointer_updated":False}
        with (
            patch("rag.runtime.auto_index_incremental_fenced.renew_index_supervisor",
                  side_effect=renew),
            patch("rag.runtime.auto_index_incremental_fenced.production_generation_lock",
                  return_value=nullcontext()),
            patch("rag.runtime.auto_index_incremental_fenced.transfer_verified_incremental_batch",
                  side_effect=slow),
            self.assertRaisesRegex(RuntimeError,"fencing lost"),
        ):
            execute_fenced_incremental_batch(
                **self.kwargs,heartbeat_seconds=1)

    def test_heartbeat_bounds_refuse_invalid_intervals(self):
        with patch("rag.runtime.auto_index_incremental_fenced.renew_index_supervisor") as renew:
            for interval in (0,61,True,float("nan")):
                with self.subTest(interval=interval),self.assertRaises(ValueError):
                    execute_fenced_incremental_batch(
                        **self.kwargs,heartbeat_seconds=interval)
            renew.assert_not_called()

    def test_lost_fence_after_write_demands_audit(self):
        with (
            patch("rag.runtime.auto_index_incremental_fenced.renew_index_supervisor",
                  side_effect=[{"accepted":True},{"accepted":False}]),
            patch("rag.runtime.auto_index_incremental_fenced.production_generation_lock",return_value=nullcontext()),
            patch("rag.runtime.auto_index_incremental_fenced.transfer_verified_incremental_batch",
                  return_value={"vectors_written":1}),
            self.assertRaisesRegex(RuntimeError,"fencing lost"),
        ):
            execute_fenced_incremental_batch(**self.kwargs)
