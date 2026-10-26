"""RAG-AUTO-01.5: durable pause/resume/cancel tests."""
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from rag.runtime.auto_index_queue import (
    AutoIndexQueueError,create_draft,default_queue_path,get_job,list_events,
)
from rag.runtime.auto_index_approval import (
    approve_auto_index_draft,build_auto_index_preview,
)
from rag.runtime.auto_index_controls import request_auto_index_control
from rag.runtime.auto_index_supervisor import (
    inspect_index_supervisor,reserve_index_supervisor,
    renew_index_supervisor,
)


class AutoIndexControlTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)/"files"
        self.root.mkdir()
        self.source=self.root/"main.py"
        self.source.write_text("print('good')\n",encoding="utf-8")
        self.db=default_queue_path(Path(tmp.name))
        self.job=create_draft(
            self.db,project_id="project-test",source_root=self.root,
            idempotency_key="control-123456789",allow_write=True,
        )
        preview=build_auto_index_preview("project-test",self.root)
        approve_auto_index_draft(
            self.db,self.job["job_id"],preview,
            confirmed_digest=preview["review_sha256"],
            operator_approved=True,allow_write=True,
        )

    def control(self,action,**kwargs):
        params=dict(operator_requested=True,control_enabled=True,now_epoch=200)
        params.update(kwargs)
        return request_auto_index_control(self.db,self.job["job_id"],action,**params)

    def test_pause_resume_cancel_without_worker(self):
        self.assertEqual(self.control("PAUSE")["state"],"PAUSED")
        self.assertEqual(get_job(self.db,self.job["job_id"])["state"],"PAUSED")
        self.assertEqual(self.control("RESUME")["state"],"QUEUED")
        self.assertEqual(self.control("CANCEL")["state"],"CANCELLED")
        self.assertEqual(get_job(self.db,self.job["job_id"])["state"],"CANCELLED")
        self.assertEqual(list_events(self.db,self.job["job_id"])[-1]["event_type"],"CONTROL_CANCEL")
        with self.assertRaises(AutoIndexQueueError):
            self.control("RESUME")

    def test_pause_invalidates_unstarted_reservation(self):
        reserved=reserve_index_supervisor(
            self.db,self.job["job_id"],operator_approved=True,
            reservation_enabled=True,now_epoch=100,
        )
        self.assertEqual(reserved["state"],"RESERVED_NO_WORKER")
        self.assertEqual(self.control("PAUSE",now_epoch=101)["state"],"PAUSED")
        self.assertEqual(inspect_index_supervisor(self.db)["state"],"NOT_RESERVED")
        heartbeat=renew_index_supervisor(
            self.db,self.job["job_id"],reserved["lease_token"],
            reserved["generation"],now_epoch=102,
        )
        self.assertFalse(heartbeat["accepted"])

    def test_cancel_invalidates_unstarted_reservation(self):
        reserved=reserve_index_supervisor(
            self.db,self.job["job_id"],operator_approved=True,
            reservation_enabled=True,now_epoch=100,
        )
        self.control("CANCEL",now_epoch=101)
        self.assertEqual(inspect_index_supervisor(self.db)["state"],"NOT_RESERVED")
        self.assertFalse(renew_index_supervisor(
            self.db,self.job["job_id"],reserved["lease_token"],
            reserved["generation"],now_epoch=102,
        )["accepted"])

    def test_resuming_modified_source_is_refused(self):
        self.control("PAUSE")
        self.source.write_text("print('different')\n",encoding="utf-8")
        with self.assertRaises(ValueError):
            self.control("RESUME")
        self.assertEqual(get_job(self.db,self.job["job_id"])["state"],"PAUSED")

    def test_permission_gate_prevents_mutation(self):
        with self.assertRaises(PermissionError):
            self.control("PAUSE",operator_requested=False)
        with self.assertRaises(PermissionError):
            self.control("CANCEL",control_enabled=False)
        self.assertEqual(get_job(self.db,self.job["job_id"])["state"],"QUEUED")

    def test_running_pause_is_request_only(self):
        with closing(sqlite3.connect(self.db)) as cn:
            cn.execute("UPDATE auto_jobs SET state='RUNNING' WHERE job_id=?",
                       (self.job["job_id"],))
            cn.commit()
        paused=self.control("PAUSE")
        self.assertEqual(paused["state"],"PAUSE_REQUESTED")
        self.assertTrue(paused["requires_worker_ack"])
        self.assertFalse(paused["stopped_at_safe_boundary"])
        self.assertEqual(self.control("CANCEL")["state"],"CANCEL_REQUESTED")

    def test_unknown_action_rejected(self):
        with self.assertRaises(ValueError):
            self.control("FORCE_STOP")


if __name__=="__main__":
    unittest.main()
