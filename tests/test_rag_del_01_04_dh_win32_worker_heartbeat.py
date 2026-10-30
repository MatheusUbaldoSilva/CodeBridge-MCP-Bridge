"""RAG-DEL-01.04-DH: real Win32 semantic worker and SQLite heartbeat race."""
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
import sqlite3
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

from rag.runtime.production_generation_lock import (
    production_generation_lock, ProductionGenerationBusy,
)
from rag.runtime.knowledge_deletion_writer_fence_lab import (
    laboratory_writer_fence, DeletionWriterFenceBlocked,
)
from rag.runtime.knowledge_deletion_reservation_freeze_lab import (
    freeze_deletion_reservations_lab,
)
from rag.runtime.knowledge_deletion_supervisor_review import (
    inspect_deletion_supervisor_read_only,
)


_SEMANTIC_WORKER = r"""
from pathlib import Path
from unittest.mock import patch
import sqlite3
import sys
import threading
from rag.runtime.production_generation_lock import production_generation_lock

root, queue = Path(sys.argv[1]), Path(sys.argv[2])
done = threading.Event()

def heartbeat():
    while not done.wait(0.05):
        try:
            with sqlite3.connect(queue,timeout=0.15,isolation_level=None) as db:
                db.execute("BEGIN IMMEDIATE")
                db.execute("UPDATE heartbeat SET count=count+1 WHERE singleton=1")
                db.execute("COMMIT")
        except sqlite3.Error:
            pass

with patch("rag.runtime.production_generation_lock.resolve_rag_sqlite_path",
           return_value=root/"rag_index.sqlite3"):
    with production_generation_lock(exclusive=True,channel="semantic"):
        thread=threading.Thread(target=heartbeat,daemon=True)
        thread.start()
        print("SEMANTIC_HELD",flush=True)
        sys.stdin.readline()
        done.set()
        thread.join(timeout=2)
"""


class Win32SemanticHeartbeatTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.rag = self.root / "CodeBridge" / "rag"
        self.rag.mkdir(parents=True)
        self.queue = self.root / "auto" / "jobs" / "auto_index_jobs.sqlite3"
        self.queue.parent.mkdir(parents=True)
        with closing(sqlite3.connect(self.queue)) as db:
            db.execute("PRAGMA user_version=1")
            db.execute("CREATE TABLE auto_worker_lease "
                       "(singleton INTEGER PRIMARY KEY,job_id TEXT,lease_token TEXT,"
                       "lease_until_epoch REAL,generation INTEGER)")
            db.execute("INSERT INTO auto_worker_lease VALUES (1,NULL,NULL,NULL,1)")
            db.execute("CREATE TABLE auto_jobs (job_id TEXT,state TEXT)")
            db.execute("CREATE TABLE heartbeat (singleton INTEGER PRIMARY KEY,"
                       "count INTEGER NOT NULL)")
            db.execute("INSERT INTO heartbeat VALUES (1,0)")
            db.commit()

    def start_worker(self):
        proc = subprocess.Popen(
            [sys.executable, "-c", _SEMANTIC_WORKER,
             str(self.rag), str(self.queue)],
            cwd=str(Path(__file__).resolve().parents[1]),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True,
        )
        if proc.stdout.readline().strip() != "SEMANTIC_HELD":
            err = proc.stderr.read()
            raise AssertionError("semantic worker failed: " + err)
        return proc

    def guards(self):
        return (
            lambda: production_generation_lock(exclusive=True,channel="generation"),
            lambda: production_generation_lock(exclusive=True,channel="semantic"),
        )

    def fence(self, **kwargs):
        gen, sem = self.guards()
        return laboratory_writer_fence(
            self.queue, gen, sem,
            laboratory_mode=True, operator_approved=True,
            **kwargs,
        )

    def pulses(self):
        with closing(sqlite3.connect(self.queue)) as db:
            return db.execute("SELECT count FROM heartbeat WHERE singleton=1").fetchone()[0]

    def test_semantic_conflict_fails_without_blocking_heartbeat(self):
        proc = self.start_worker()
        try:
            with patch("rag.runtime.production_generation_lock.resolve_rag_sqlite_path",
                       return_value=self.rag/"rag_index.sqlite3"):
                time.sleep(0.12)
                before = self.pulses()
                with self.assertRaises(ProductionGenerationBusy):
                    with self.fence():
                        self.fail("cannot enter fence under foreign semantic lock")
                time.sleep(0.15)
                self.assertGreater(self.pulses(), before)
                with production_generation_lock(
                    exclusive=True, channel="generation"
                ):
                    pass
                with closing(sqlite3.connect(self.queue, timeout=0.1)) as db:
                    db.execute("BEGIN IMMEDIATE")
                    db.rollback()
        finally:
            if proc.poll() is None:
                try:
                    proc.communicate(input="\n", timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.communicate(timeout=5)
        with patch("rag.runtime.production_generation_lock.resolve_rag_sqlite_path",
                   return_value=self.rag/"rag_index.sqlite3"):
            with self.fence() as state:
                self.assertEqual(state["lock_order"],
                                 ["generation","semantic","queue"])
        self.assertEqual(proc.returncode, 0)

    def test_worker_crash_releases_win32_but_stale_lease_blocks_cutover(self):
        freeze = freeze_deletion_reservations_lab(
            self.queue, laboratory_mode=True, operator_approved=True,
        )
        with closing(sqlite3.connect(self.queue)) as db:
            db.execute(
                "UPDATE auto_worker_lease SET job_id='orphan',"
                "lease_token='0123456789abcdef0123456789abcdef',"
                "lease_until_epoch=1 WHERE singleton=1"
            )
            db.commit()
        proc = self.start_worker()
        proc.kill()
        proc.communicate(timeout=5)
        self.assertNotEqual(proc.returncode, 0)
        with patch("rag.runtime.production_generation_lock.resolve_rag_sqlite_path",
                   return_value=self.rag/"rag_index.sqlite3"):
            with self.assertRaisesRegex(
                DeletionWriterFenceBlocked, "lease requires separate reconciliation"
            ):
                with self.fence(
                    expected_freeze_generation=freeze["freeze_generation"],
                ):
                    self.fail("expired lease cannot be ignored after worker crash")
        review = inspect_deletion_supervisor_read_only(self.queue, now_epoch=100)
        self.assertEqual(review["lease_status"], "EXPIRED_RECONCILIATION_REQUIRED")
        self.assertTrue(review["reservation_freeze_active"])
        self.assertFalse(review["activation_authorized"])
        self.assertGreaterEqual(self.pulses(), 0)