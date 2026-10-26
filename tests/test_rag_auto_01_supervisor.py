"""RAG-AUTO-01.4 exclusive supervisor lease regression tests."""
from pathlib import Path
import tempfile
import unittest

from rag.runtime.auto_index_queue import create_draft,default_queue_path
from rag.runtime.auto_index_approval import (
    build_auto_index_preview,approve_auto_index_draft,
)
from rag.runtime.auto_index_supervisor import (
    inspect_index_supervisor,reserve_index_supervisor,
    release_index_supervisor,renew_index_supervisor,validate_job_sources,
)


class AutoSupervisorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/"project"
        self.root.mkdir()
        (self.root/"main.py").write_text("print('safe')\n",encoding="utf-8")
        self.db=default_queue_path(Path(self.tmp.name))
        self.job=self._approved_job("alpha","request-supervisor-1234")

    def _approved_job(self,project,key):
        job=create_draft(self.db,project_id=project,source_root=self.root,
                         idempotency_key=key,allow_write=True)
        review=build_auto_index_preview(project,self.root)
        approve_auto_index_draft(
            self.db,job["job_id"],review,confirmed_digest=review["review_sha256"],
            operator_approved=True,allow_write=True,
        )
        return job

    def reserve(self,job=None,now=100,**options):
        return reserve_index_supervisor(
            self.db,(job or self.job)["job_id"],now_epoch=now,
            reservation_enabled=True,operator_approved=True,**options,
        )

    def test_only_authorized_reservations(self):
        with self.assertRaises(PermissionError):
            reserve_index_supervisor(self.db,self.job["job_id"])
        self.assertEqual(inspect_index_supervisor(self.db)["state"],"NOT_RESERVED")

    def test_one_owner_across_projects(self):
        a=self.reserve()
        self.assertEqual(a["state"],"RESERVED_NO_WORKER")
        self.assertFalse(a["worker_started"])
        self.assertFalse(a["publication_authorized"])
        bjob=self._approved_job("beta","request-supervisor-5678")
        b=self.reserve(bjob,now=105)
        self.assertEqual(b["state"],"SUPERVISOR_BUSY")
        self.assertEqual(b["owner_job_id"],self.job["job_id"])
        self.assertEqual(inspect_index_supervisor(self.db)["job_id"],self.job["job_id"])

    def test_release_and_new_generation(self):
        old=self.reserve(now=100)
        release=release_index_supervisor(
            self.db,self.job["job_id"],old["lease_token"],old["generation"],
            now_epoch=105,
        )
        self.assertTrue(release["accepted"])
        newer=self.reserve(now=106)
        self.assertEqual(newer["generation"],old["generation"]+1)
        self.assertNotEqual(newer["lease_token"],old["lease_token"])
        stale=renew_index_supervisor(
            self.db,self.job["job_id"],old["lease_token"],old["generation"],
            now_epoch=107,
        )
        self.assertFalse(stale["accepted"])

    def test_stale_takeover_does_not_honor_old_owner(self):
        first=self.reserve(now=100,lease_seconds=20)
        next_owner=self.reserve(now=121)
        self.assertEqual(next_owner["generation"],first["generation"]+1)
        stale=release_index_supervisor(
            self.db,self.job["job_id"],first["lease_token"],
            first["generation"],now_epoch=122,
        )
        self.assertEqual(stale["state"],"STALE_SUPERVISOR")
        self.assertEqual(inspect_index_supervisor(self.db)["generation"],next_owner["generation"])

    def test_heartbeat_only_from_valid_owner(self):
        a=self.reserve(now=100,lease_seconds=15)
        renewed=renew_index_supervisor(
            self.db,self.job["job_id"],a["lease_token"],a["generation"],
            now_epoch=105,lease_seconds=60,
        )
        self.assertTrue(renewed["accepted"])
        self.assertEqual(renewed["lease_until_epoch"],165)
        self.assertEqual(self.reserve(now=130)["state"],"SUPERVISOR_BUSY")

    def test_source_changed_prevents_reservation(self):
        (self.root/"main.py").write_text("print('new content')",encoding="utf-8")
        with self.assertRaises(ValueError):
            self.reserve()
        self.assertEqual(inspect_index_supervisor(self.db)["state"],"NOT_RESERVED")

    def test_no_claim_for_inert_draft(self):
        draft=create_draft(
            self.db,project_id="drafted",source_root=self.root,
            idempotency_key="another-draft-12345",allow_write=True,
        )
        with self.assertRaises(Exception):
            self.reserve(draft)
        self.assertEqual(inspect_index_supervisor(self.db)["state"],"NOT_RESERVED")


if __name__=="__main__":
    unittest.main()
