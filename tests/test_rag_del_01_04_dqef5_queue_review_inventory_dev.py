"""DQ-E-F-5 ready-for-review queue metadata read-only tests."""
from contextlib import closing
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from unittest import TestCase
from rag.runtime.knowledge_deletion_queue_review_inventory_dev import inspect_pending_review_jobs_dev

class ReviewQueueInventoryDevTests(TestCase):
    def setUp(self):
        t=TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.q=Path(t.name)/"auto"/"jobs"/"auto_index_jobs.sqlite3"
        self.q.parent.mkdir(parents=True)
        with closing(sqlite3.connect(self.q)) as db:
            db.execute("CREATE TABLE auto_jobs(job_id TEXT,project_id TEXT,state TEXT,approved INTEGER,candidate_generation TEXT)")
            db.execute("PRAGMA user_version=1")
            db.commit()
    def seed(self,state):
        with closing(sqlite3.connect(self.q)) as db:
            db.execute("INSERT INTO auto_jobs VALUES (?,?,?,?,?)",
                       ("raw-job-id","newworldpvp",state,1,"candidate"))
            db.commit()
    def test_empty_queue_remains_no_auth(self):
        r=inspect_pending_review_jobs_dev(self.q)
        self.assertEqual(r["state"],"AUTO_REVIEW_QUEUE_INVENTORY_EMPTY_READ_ONLY")
        self.assertFalse(r["activation_authorized"])
    def test_ready_for_review_blocks_without_disclosing_id(self):
        self.seed("READY_FOR_REVIEW")
        r=inspect_pending_review_jobs_dev(self.q)
        self.assertIn("PENDING_REVIEW_JOBS_PRESENT",r["blockers"])
        self.assertEqual(r["pending_jobs"][0]["state"],"READY_FOR_REVIEW")
        self.assertNotIn("raw-job-id",str(r))
    def test_cancelled_ignored(self):
        self.seed("CANCELLED")
        self.assertEqual(inspect_pending_review_jobs_dev(self.q)["pending_jobs"],[])
    def test_running_blocks(self):
        self.seed("RUNNING")
        self.assertIn("PENDING_REVIEW_JOBS_PRESENT",inspect_pending_review_jobs_dev(self.q)["blockers"])
    def test_missing_queue_blocks(self):
        self.q.unlink()
        self.assertIn("QUEUE_READ_UNVERIFIED",inspect_pending_review_jobs_dev(self.q)["blockers"])
    def test_bad_schema_blocks(self):
        with closing(sqlite3.connect(self.q)) as db:
            db.execute("PRAGMA user_version=2")
            db.commit()
        self.assertIn("QUEUE_READ_UNVERIFIED",inspect_pending_review_jobs_dev(self.q)["blockers"])
