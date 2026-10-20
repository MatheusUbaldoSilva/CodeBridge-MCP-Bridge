"""Offline opt-in one-shot worker integration tests; no live models."""
from tests.test_incremental_worker_receipt import OfflineStagingReceiptTests
from rag.runtime.incremental_offline_worker import process_offline_job_once
from rag.runtime.incremental_job_queue import inspect_job_queue

class OfflineConsumerTests(OfflineStagingReceiptTests):
    def test_default_disabled_does_not_create_db(self):
        result=process_offline_job_once(self.db,self.root,
            approved_paths=("sample.py",))
        self.assertEqual(result["state"],"OFFLINE_WORKER_DISABLED")
        self.assertFalse(self.db.exists())

    def test_fake_builder_stages_and_acks(self):
        self.enqueue(queue_enabled=True,now_epoch=140)
        calls=[]
        def builder(plan):
            calls.append(plan)
            return {"state":"STAGED_NOT_PUBLISHED","staging_path":str(self.make_stage())}
        result=process_offline_job_once(
            self.db,self.root,approved_paths=("sample.py",),
            queue_enabled=True,worker_enabled=True,builder=builder,now_epoch=141)
        self.assertEqual(result["state"],"STAGED_OFFLINE_VALIDATED")
        self.assertFalse(result["active_index_updated"])
        self.assertEqual(len(calls),1)
        self.assertEqual(inspect_job_queue(self.db)["by_state"],
                         {"STAGED_OFFLINE_VALIDATED":1})

    def test_builder_failure_retries_without_publish(self):
        self.enqueue(queue_enabled=True,now_epoch=140)
        def builder(_):
            raise RuntimeError("synthetic model failure")
        result=process_offline_job_once(
            self.db,self.root,approved_paths=("sample.py",),
            queue_enabled=True,worker_enabled=True,builder=builder,now_epoch=141)
        self.assertEqual(result["state"],"SCHEDULED_RETRY")
        self.assertEqual(inspect_job_queue(self.db)["by_state"],{"RETRY":1})
        self.assertFalse(result["safe_to_publish"])
