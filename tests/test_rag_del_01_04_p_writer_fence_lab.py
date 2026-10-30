"""RAG-DEL-01.04-P: reservation barrier and two-lock order, scratch only."""
from contextlib import closing, contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
import sqlite3
import subprocess
import sys

from rag.runtime.knowledge_deletion_writer_fence_lab import (
    DeletionWriterFenceBlocked, laboratory_writer_fence,
)


class ScratchWriterFenceTests(TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.queue = self.root / "auto" / "jobs" / "auto_index_jobs.sqlite3"
        self.queue.parent.mkdir(parents=True)
        with closing(sqlite3.connect(self.queue)) as db:
            db.execute(
                "CREATE TABLE auto_worker_lease "
                "(singleton INTEGER PRIMARY KEY,job_id TEXT,lease_token TEXT,"
                "lease_until_epoch REAL,generation INTEGER)"
            )
            db.execute("INSERT INTO auto_worker_lease VALUES (1,NULL,NULL,NULL,2)")
            db.execute("CREATE TABLE auto_jobs (job_id TEXT,state TEXT)")
            db.execute("PRAGMA user_version=1")
            db.commit()
        self.events = []

    def guards(self):
        @contextmanager
        def generation():
            self.events.append("generation+")
            try:
                yield
            finally:
                self.events.append("generation-")

        @contextmanager
        def semantic():
            self.events.append("semantic+")
            try:
                yield
            finally:
                self.events.append("semantic-")

        return generation, semantic

    def fence(self):
        gen, sem = self.guards()
        return laboratory_writer_fence(
            self.queue, gen, sem, laboratory_mode=True, operator_approved=True
        )

    def test_order_and_denial_of_operational_use(self):
        with self.fence() as result:
            self.assertEqual(result["lock_order"], ["queue", "generation", "semantic"])
            self.assertFalse(result["activation_authorized"])
            self.assertFalse(result["operational_use_allowed"])
            self.assertEqual(result["supervisor_generation"], 2)
            self.assertEqual(self.events, ["generation+", "semantic+"])
        self.assertEqual(
            self.events,
            ["generation+", "semantic+", "semantic-", "generation-"],
        )

    def test_second_process_cannot_reserve_during_barrier(self):
        probe = (
            "import sqlite3,sys; "
            "c=sqlite3.connect(sys.argv[1],timeout=0.1,isolation_level=None); "
            "c.execute('BEGIN IMMEDIATE'); c.execute('ROLLBACK')"
        )
        with self.fence():
            completed = subprocess.run(
                [sys.executable, "-c", probe, str(self.queue)],
                capture_output=True, text=True, timeout=5,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("locked", completed.stderr.lower())
        completed = subprocess.run(
            [sys.executable, "-c", probe, str(self.queue)],
            capture_output=True, text=True, timeout=5,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_active_lease_rejected(self):
        with closing(sqlite3.connect(self.queue)) as db:
            db.execute(
                "UPDATE auto_worker_lease SET job_id='running',"
                "lease_token='token',lease_until_epoch=9999999999"
            )
            db.commit()
        with self.assertRaises(DeletionWriterFenceBlocked):
            with self.fence():
                self.fail("cannot enter while reserved")
        self.assertEqual(self.events, [])

    def test_expired_lease_also_rejected(self):
        with closing(sqlite3.connect(self.queue)) as db:
            db.execute(
                "UPDATE auto_worker_lease SET job_id='stale',"
                "lease_token='old',lease_until_epoch=1"
            )
            db.commit()
        with self.assertRaisesRegex(DeletionWriterFenceBlocked, "reconciliation"):
            with self.fence():
                pass

    def test_runnable_job_rejected(self):
        with closing(sqlite3.connect(self.queue)) as db:
            db.execute("INSERT INTO auto_jobs VALUES ('pending','QUEUED')")
            db.commit()
        with self.assertRaisesRegex(DeletionWriterFenceBlocked, "runnable"):
            with self.fence():
                pass

    def test_untrusted_schema_rejected(self):
        with closing(sqlite3.connect(self.queue)) as db:
            db.execute("DROP TABLE auto_worker_lease")
            db.commit()
        with self.assertRaisesRegex(DeletionWriterFenceBlocked, "tables missing"):
            with self.fence():
                pass

    def test_no_mode_or_approval(self):
        gen, sem = self.guards()
        for lab, approved in [(False, True), (True, False)]:
            with self.assertRaises(PermissionError):
                with laboratory_writer_fence(
                    self.queue, gen, sem,
                    laboratory_mode=lab, operator_approved=approved
                ):
                    pass
        self.assertEqual(self.events, [])

    def test_providers_mandatory(self):
        _, sem = self.guards()
        with self.assertRaises(DeletionWriterFenceBlocked):
            with laboratory_writer_fence(
                self.queue, None, sem,
                laboratory_mode=True, operator_approved=True
            ):
                pass

    def test_missing_queue_never_created(self):
        self.queue.unlink()
        with self.assertRaises(DeletionWriterFenceBlocked):
            with self.fence():
                pass
        self.assertFalse(self.queue.exists())

    def test_failure_inside_fence_releases_both_guards_and_queue(self):
        with self.assertRaisesRegex(ValueError, "injected"):
            with self.fence():
                raise ValueError("injected")
        self.assertEqual(self.events[-2:], ["semantic-", "generation-"])
        with closing(sqlite3.connect(self.queue, timeout=0.1)) as db:
            db.execute("BEGIN IMMEDIATE")
            db.rollback()

    def test_external_queue_path_refused(self):
        gen, sem = self.guards()
        other = self.root / "outside.sqlite3"
        other.write_bytes(self.queue.read_bytes())
        with self.assertRaises(DeletionWriterFenceBlocked):
            with laboratory_writer_fence(
                other, gen, sem,
                laboratory_mode=True, operator_approved=True
            ):
                pass