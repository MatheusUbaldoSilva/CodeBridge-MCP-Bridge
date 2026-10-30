"""RAG-DEL-01.04-Z: real multi-process reservation/freeze serialization."""
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
import sqlite3
import subprocess
import sys

from rag.runtime.knowledge_deletion_reservation_freeze_lab import (
    DeletionReservationFreezeError, freeze_deletion_reservations_lab,
    thaw_deletion_reservations_lab,
)


_LOCKER = r"""
import sqlite3,sys
db=sqlite3.connect(sys.argv[1],isolation_level=None,timeout=5)
db.execute("BEGIN IMMEDIATE")
print("LOCKED",flush=True)
sys.stdin.readline()
db.execute("ROLLBACK")
db.close()
"""


class ScratchFreezeRaceTests(TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.queue = self.root / "auto" / "jobs" / "auto_index_jobs.sqlite3"
        self.queue.parent.mkdir(parents=True)
        with closing(sqlite3.connect(self.queue)) as db:
            db.execute("PRAGMA user_version=1")
            db.execute("CREATE TABLE auto_worker_lease "
                       "(singleton INTEGER PRIMARY KEY,job_id TEXT,lease_token TEXT,"
                       "lease_until_epoch REAL,generation INTEGER)")
            db.execute("INSERT INTO auto_worker_lease VALUES (1,NULL,NULL,NULL,1)")
            db.execute("CREATE TABLE auto_jobs (job_id TEXT,state TEXT)")
            db.commit()

    def test_active_sqlite_reservation_barrier_prevents_freeze_write(self):
        proc = subprocess.Popen(
            [sys.executable, "-c", _LOCKER, str(self.queue)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True,
        )
        try:
            self.assertEqual(proc.stdout.readline().strip(), "LOCKED")
            with self.assertRaisesRegex(DeletionReservationFreezeError, "busy"):
                freeze_deletion_reservations_lab(
                    self.queue, operator_approved=True, laboratory_mode=True,
                )
            with closing(sqlite3.connect(self.queue)) as db:
                marker = db.execute(
                    "SELECT count(*) FROM sqlite_master "
                    "WHERE name='auto_deletion_reservation_freeze'"
                ).fetchone()[0]
            self.assertEqual(marker, 0)
        finally:
            if proc.poll() is None:
                try:
                    proc.communicate(input="\n", timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.communicate(timeout=5)
        freeze = freeze_deletion_reservations_lab(
            self.queue, operator_approved=True, laboratory_mode=True,
        )
        self.assertEqual(freeze["state"], "LAB_RESERVATIONS_FROZEN")
        self.assertEqual(
            thaw_deletion_reservations_lab(
                self.queue, freeze["freeze_token"], freeze["freeze_generation"],
                operator_approved=True, laboratory_mode=True,
            )["state"], "LAB_RESERVATIONS_OPEN",
        )

    def test_thaw_blocked_by_foreign_held_sqlite_barrier(self):
        freeze = freeze_deletion_reservations_lab(
            self.queue, operator_approved=True, laboratory_mode=True,
        )
        proc = subprocess.Popen(
            [sys.executable, "-c", _LOCKER, str(self.queue)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True,
        )
        try:
            self.assertEqual(proc.stdout.readline().strip(), "LOCKED")
            with self.assertRaisesRegex(DeletionReservationFreezeError, "busy"):
                thaw_deletion_reservations_lab(
                    self.queue, freeze["freeze_token"], freeze["freeze_generation"],
                    operator_approved=True, laboratory_mode=True,
                )
        finally:
            if proc.poll() is None:
                try:
                    proc.communicate(input="\n", timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.communicate(timeout=5)
        thaw = thaw_deletion_reservations_lab(
            self.queue, freeze["freeze_token"], freeze["freeze_generation"],
            operator_approved=True, laboratory_mode=True,
        )
        self.assertEqual(thaw["state"], "LAB_RESERVATIONS_OPEN")