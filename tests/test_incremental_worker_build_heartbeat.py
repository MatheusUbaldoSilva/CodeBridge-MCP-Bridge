"""Long-build heartbeat proof using real monotonic wall-clock tests."""
from tests.test_incremental_worker_receipt import OfflineStagingReceiptTests
from unittest.mock import patch
from rag.runtime.incremental_offline_worker import process_offline_job_once
from rag.runtime.incremental_job_queue import renew_job_lease,inspect_job_queue
import time

class HeartbeatDuringBuildTests(OfflineStagingReceiptTests):
    def test_lease_renews_during_delayed_staging(self):
        self.enqueue(queue_enabled=True,now_epoch=time.time()-1,
                     changed_at_epoch=time.time()-60,debounce_seconds=0)
        calls=[]
        def spy(*args, **kw):
            value=renew_job_lease(*args,**kw)
            calls.append(value["state"])
            return value
        def slow_builder(plan):
            time.sleep(0.14)
            return {"state":"STAGED_NOT_PUBLISHED",
                    "staging_path":str(self.make_stage())}
        with patch("rag.runtime.incremental_offline_worker.renew_job_lease",side_effect=spy):
            result=process_offline_job_once(
                self.db,self.root,approved_paths=("sample.py",),
                queue_enabled=True,worker_enabled=True,builder=slow_builder,
                heartbeat_interval_seconds=0.02)
        self.assertEqual(result["state"],"STAGED_OFFLINE_VALIDATED")
        self.assertIn("LEASE_RENEWED",calls)

    def test_failure_to_renew_blocks_acknowledgment(self):
        self.enqueue(queue_enabled=True,now_epoch=time.time()-1,
                     changed_at_epoch=time.time()-60,debounce_seconds=0)
        def slow_builder(plan):
            time.sleep(0.12)
            return {"state":"STAGED_NOT_PUBLISHED",
                    "staging_path":str(self.make_stage())}
        with patch("rag.runtime.incremental_offline_worker.renew_job_lease",
                   return_value={"state":"STALE_OR_EXPIRED_LEASE","renewed":False}):
            result=process_offline_job_once(
                self.db,self.root,approved_paths=("sample.py",),
                queue_enabled=True,worker_enabled=True,builder=slow_builder,
                heartbeat_interval_seconds=0.02)
        self.assertEqual(result["state"],"SCHEDULED_RETRY")
        self.assertEqual(inspect_job_queue(self.db)["by_state"],{"RETRY":1})
