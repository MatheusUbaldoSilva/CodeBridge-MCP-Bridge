"""RAG-DEL-01.04-S: real Windows LockFileEx, forced into a temp-only RAG root."""
import json
from contextlib import closing
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from rag.runtime.production_generation_lock import (
    ProductionGenerationBusy, production_generation_lock,
)
from rag.runtime.knowledge_deletion_writer_fence_lab import laboratory_writer_fence


CHILD_PROBE = r"""
from pathlib import Path
import sys
from unittest.mock import patch
from rag.runtime.production_generation_lock import production_generation_lock
state = Path(sys.argv[1])
channel = sys.argv[2]
with patch("rag.runtime.production_generation_lock.resolve_rag_sqlite_path",
           return_value=state/"rag_index.sqlite3"):
    with production_generation_lock(exclusive=True,channel=channel):
        print("HELD",flush=True)
"""


class WindowsDualLockLabTests(TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.production_facsimile = self.root / "CodeBridge" / "rag"
        self.production_facsimile.mkdir(parents=True)
        self.queue = self.root / "auto" / "jobs" / "auto_index_jobs.sqlite3"
        self.queue.parent.mkdir(parents=True)
        with closing(sqlite3.connect(self.queue)) as db:
            db.execute("CREATE TABLE auto_worker_lease "
                       "(singleton INTEGER PRIMARY KEY,job_id TEXT,lease_token TEXT,"
                       "lease_until_epoch REAL,generation INTEGER)")
            db.execute("INSERT INTO auto_worker_lease VALUES (1,NULL,NULL,NULL,1)")
            db.execute("CREATE TABLE auto_jobs (job_id TEXT,state TEXT)")
            db.execute("PRAGMA user_version=1")
            db.commit()

    def _guard(self, channel):
        return lambda: production_generation_lock(exclusive=True, channel=channel)

    def fence(self):
        return laboratory_writer_fence(
            self.queue, self._guard("generation"), self._guard("semantic"),
            laboratory_mode=True, operator_approved=True,
        )

    def probe(self, channel):
        return subprocess.run(
            [sys.executable, "-c", CHILD_PROBE,
             str(self.production_facsimile), channel],
            cwd=str(Path(__file__).resolve().parents[1]),
            capture_output=True, text=True, timeout=10,
        )

    def test_both_actual_lockfileex_channels_reject_second_process(self):
        with patch("rag.runtime.production_generation_lock.resolve_rag_sqlite_path",
                   return_value=self.production_facsimile / "rag_index.sqlite3"):
            with self.fence():
                for channel in ("generation", "semantic"):
                    result = self.probe(channel)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("ProductionGenerationBusy", result.stderr)
            for channel in ("generation", "semantic"):
                result = self.probe(channel)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("HELD", result.stdout)
        self.assertTrue((self.production_facsimile /
                         "production-generation.lock").is_file())
        self.assertTrue((self.production_facsimile /
                         "production-semantic.lock").is_file())

    def test_second_lock_busy_releases_first_and_queue_barrier(self):
        code = r"""
from pathlib import Path
import sys
from unittest.mock import patch
from rag.runtime.production_generation_lock import production_generation_lock
state=Path(sys.argv[1])
with patch("rag.runtime.production_generation_lock.resolve_rag_sqlite_path",
           return_value=state/"rag_index.sqlite3"):
    with production_generation_lock(exclusive=True,channel="semantic"):
        print("READY",flush=True)
        sys.stdin.readline()
"""
        proc = subprocess.Popen(
            [sys.executable, "-c", code, str(self.production_facsimile)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, cwd=str(Path(__file__).resolve().parents[1]),
        )
        try:
            self.assertEqual(proc.stdout.readline().strip(), "READY")
            with patch("rag.runtime.production_generation_lock.resolve_rag_sqlite_path",
                       return_value=self.production_facsimile / "rag_index.sqlite3"):
                with self.assertRaises(ProductionGenerationBusy):
                    with self.fence():
                        self.fail("semantic channel should be busy")
                # Generation was acquired before semantic, but was released.
                with production_generation_lock(exclusive=True, channel="generation"):
                    pass
            with closing(sqlite3.connect(self.queue,timeout=0.1)) as db:
                db.execute("BEGIN IMMEDIATE")
                db.rollback()
        finally:
            if proc.poll() is None:
                try:
                    proc.communicate(input="\n",timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.communicate(timeout=5)