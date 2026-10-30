"""RAG-DEL-01.04-T: read-only AUTO supervisor evidence in synthetic queues."""
from contextlib import closing
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from unittest import TestCase

from rag.runtime.knowledge_deletion_supervisor_review import (
    DeletionSupervisorReviewError, inspect_deletion_supervisor_read_only,
)


class SupervisorObservationTests(TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.queue = self.root / "auto" / "jobs" / "auto_index_jobs.sqlite3"
        self.queue.parent.mkdir(parents=True)

    def seed(self, *, version=1, lease=True, jobs=True):
        with closing(sqlite3.connect(self.queue)) as db:
            if lease:
                db.execute("CREATE TABLE auto_worker_lease "
                           "(singleton INTEGER PRIMARY KEY,job_id TEXT,"
                           "lease_token TEXT,lease_until_epoch REAL,generation INTEGER)")
                db.execute("INSERT INTO auto_worker_lease VALUES (1,NULL,NULL,NULL,5)")
            if jobs:
                db.execute("CREATE TABLE auto_jobs (job_id TEXT,state TEXT)")
            db.execute(f"PRAGMA user_version={version}")
            db.commit()

    def review(self):
        return inspect_deletion_supervisor_read_only(self.queue)

    def test_missing_queue_is_blocked_and_not_created(self):
        evidence = self.review()
        self.assertIn("QUEUE_MISSING", evidence["blockers"])
        self.assertFalse(evidence["activation_authorized"])
        self.assertFalse(self.queue.exists())

    def test_quiet_observation_is_not_cutover_permission(self):
        self.seed()
        initial = self.queue.read_bytes()
        result = self.review()
        self.assertEqual(result["state"], "SUPERVISOR_OBSERVED_QUIET_READ_ONLY")
        self.assertTrue(result["supervisor_observed_quiet"])
        self.assertFalse(result["queue_barrier_held"])
        self.assertFalse(result["operational_use_allowed"])
        self.assertFalse(result["activation_authorized"])
        self.assertEqual(self.queue.read_bytes(), initial)

    def test_expired_lease_requires_reconciliation(self):
        self.seed()
        with closing(sqlite3.connect(self.queue)) as db:
            db.execute("UPDATE auto_worker_lease SET job_id='x',"
                       "lease_token='token',lease_until_epoch=1")
            db.commit()
        result = self.review()
        self.assertIn("LEASE_RECONCILIATION_REQUIRED", result["blockers"])
        self.assertFalse(result["supervisor_observed_quiet"])

    def test_active_lease_requires_reconciliation(self):
        self.seed()
        with closing(sqlite3.connect(self.queue)) as db:
            db.execute("UPDATE auto_worker_lease SET job_id='x',"
                       "lease_token='token',lease_until_epoch=9999999999")
            db.commit()
        self.assertIn("LEASE_RECONCILIATION_REQUIRED", self.review()["blockers"])

    def test_queued_job_blocks_without_lease(self):
        self.seed()
        with closing(sqlite3.connect(self.queue)) as db:
            db.execute("INSERT INTO auto_jobs VALUES ('job','QUEUED')")
            db.commit()
        result = self.review()
        self.assertEqual(result["job_state_counts"], {"QUEUED": 1})
        self.assertIn("UNRESOLVED_QUEUE_JOBS", result["blockers"])

    def test_draft_also_blocks(self):
        self.seed()
        with closing(sqlite3.connect(self.queue)) as db:
            db.execute("INSERT INTO auto_jobs VALUES ('job','DRAFT')")
            db.commit()
        self.assertIn("UNRESOLVED_QUEUE_JOBS", self.review()["blockers"])

    def test_completed_failed_or_cancelled_jobs_are_allowed_for_observation(self):
        self.seed()
        with closing(sqlite3.connect(self.queue)) as db:
            db.execute("INSERT INTO auto_jobs VALUES ('job','FAILED')")
            db.execute("INSERT INTO auto_jobs VALUES ('job2','CANCELLED')")
            db.commit()
        evidence = self.review()
        self.assertTrue(evidence["supervisor_observed_quiet"])
        self.assertEqual(evidence["job_state_counts"], {"CANCELLED": 1, "FAILED": 1})
        self.assertFalse(evidence["activation_authorized"])

    def test_missing_supervisor_table_is_blocked(self):
        self.seed(lease=False)
        self.assertIn("SUPERVISOR_TABLES_MISSING", self.review()["blockers"])

    def test_unsupported_schema_is_blocked(self):
        self.seed(version=99)
        self.assertIn("UNSUPPORTED_QUEUE_SCHEMA", self.review()["blockers"])

    def test_bad_path_is_rejected(self):
        other = self.root / "unexpected.db"
        other.touch()
        with self.assertRaises(DeletionSupervisorReviewError):
            inspect_deletion_supervisor_read_only(other)

    def test_malformed_supervisor_is_blocked(self):
        self.seed()
        with closing(sqlite3.connect(self.queue)) as db:
            db.execute("DELETE FROM auto_worker_lease")
            db.commit()
        self.assertIn("LEASE_SINGLETON_INVALID", self.review()["blockers"])
    def test_ready_for_review_is_not_final_deletion_quiescence(self):
        self.seed()
        with closing(sqlite3.connect(self.queue)) as db:
            db.execute("INSERT INTO auto_jobs VALUES ('pending-review','READY_FOR_REVIEW')")
            db.commit()
        evidence = self.review()
        self.assertEqual(evidence["job_state_counts"], {"READY_FOR_REVIEW": 1})
        self.assertFalse(evidence["supervisor_observed_quiet"])
        self.assertFalse(evidence["activation_authorized"])
        self.assertIn("UNRESOLVED_QUEUE_JOBS", evidence["blockers"])
    def test_freeze_marker_is_observed_without_exposing_token(self):
        from rag.runtime.knowledge_deletion_reservation_freeze_lab import (
            freeze_deletion_reservations_lab, thaw_deletion_reservations_lab,
        )
        self.seed()
        before = self.review()
        self.assertFalse(before["reservation_freeze_active"])
        freeze = freeze_deletion_reservations_lab(
            self.queue, laboratory_mode=True, operator_approved=True,
        )
        evidence = self.review()
        self.assertTrue(evidence["reservation_freeze_active"])
        self.assertEqual(
            evidence["reservation_freeze_generation"], freeze["freeze_generation"]
        )
        self.assertNotIn("freeze_token", evidence)
        self.assertTrue(evidence["supervisor_observed_quiet"])
        self.assertFalse(evidence["activation_authorized"])
        thaw_deletion_reservations_lab(
            self.queue, freeze["freeze_token"], freeze["freeze_generation"],
            laboratory_mode=True, operator_approved=True,
        )
        opened = self.review()
        self.assertFalse(opened["reservation_freeze_active"])
        self.assertGreater(
            opened["reservation_freeze_generation"],
            evidence["reservation_freeze_generation"]
        )

    def test_invalid_freeze_marker_is_reported_fail_closed(self):
        self.seed()
        with closing(sqlite3.connect(self.queue)) as db:
            db.execute("CREATE TABLE auto_deletion_reservation_freeze (wrong TEXT)")
            db.commit()
        evidence = self.review()
        self.assertIn("RESERVATION_FREEZE_MARKER_INVALID", evidence["blockers"])
        self.assertFalse(evidence["supervisor_observed_quiet"])
        self.assertFalse(evidence["activation_authorized"])