"""RAG-DEL-01.04-R: OS-process crash under scratch-only writer fencing."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from contextlib import closing
import sqlite3
import subprocess
import sys

from rag.runtime.knowledge_deletion_writer_fence_lab import laboratory_writer_fence
from rag.runtime.knowledge_deletion_recovery_plan import plan_lab_recovery
from rag.runtime.knowledge_deletion_swap_lab import laboratory_rollback


CHILD = r"""
import os, sys
from pathlib import Path
from contextlib import nullcontext
from rag.runtime.knowledge_deletion_writer_fence_lab import laboratory_writer_fence
from rag.runtime.knowledge_deletion_swap_lab import laboratory_swap, DeletionSwapError
queue, catalog, pointer, fail_at = (
    Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]
)
candidate = {"project_id": "demo", "enabled": True,
             "source_revision": "new", "generation_directory": "new"}
with laboratory_writer_fence(queue, nullcontext, nullcontext,
                             laboratory_mode=True, operator_approved=True):
    try:
        laboratory_swap("demo", "old", candidate,
                        catalog_file=catalog, public_pointer=pointer,
                        laboratory_mode=True, operator_approved=True,
                        _fail_at=fail_at)
    except DeletionSwapError:
        os._exit(47)
    os._exit(98)
"""


class CrashRecoveryFenceTests(TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
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
        self.catalog = self.root / "project-indexes.json"
        self.pointer = self.root / "active-generation.json"
        self.catalog.write_text(json.dumps({"schema_version": 1, "projects": {
            "demo": {"project_id": "demo", "enabled": True,
                     "source_revision": "old", "generation_directory": "old"},
            "other": {"project_id": "other", "enabled": True,
                      "source_revision": "other", "generation_directory": "other"}
        }}), encoding="utf-8")
        self.pointer.write_text('{"schema_version":1,"generation":"public"}',
                                encoding="utf-8")
        self.baseline = self.catalog.read_bytes()
        self.public = self.pointer.read_bytes()

    def crash_then_recover(self, mode, expected):
        process = subprocess.run(
            [sys.executable, "-c", CHILD, str(self.queue), str(self.catalog),
             str(self.pointer), mode],
            cwd=str(Path(__file__).resolve().parents[1]),
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(process.returncode, 47, process.stderr)
        plan = plan_lab_recovery(self.catalog, self.pointer)
        self.assertFalse(plan["writes_performed"])
        self.assertFalse(plan["rollback_authorized"])
        self.assertEqual(plan["plans"][0]["recommended_action"], expected)
        with laboratory_writer_fence(
            self.queue, lambda: _noop(), lambda: _noop(),
            laboratory_mode=True, operator_approved=True,
        ) as proof:
            self.assertEqual(proof["state"], "LAB_WRITER_FENCE_HELD")
            txn = plan["plans"][0]["transaction"]
            undo = laboratory_rollback(
                txn, catalog_file=self.catalog, public_pointer=self.pointer,
                operator_approved=True, laboratory_mode=True)
            self.assertIn(undo["state"], ("LAB_ROLLBACK_COMPLETE",
                                          "ALREADY_ROLLED_BACK"))
        self.assertEqual(self.catalog.read_bytes(), self.baseline)
        self.assertEqual(self.pointer.read_bytes(), self.public)
        self.assertEqual(
            json.loads(self.catalog.read_text())["projects"]["other"]["source_revision"],
            "other",
        )

    def test_process_exits_after_journal_before_swap(self):
        self.crash_then_recover("before", "RECONCILE_PREPARED_WITHOUT_SWITCH")

    def test_process_exits_after_swap_before_commit(self):
        self.crash_then_recover("after", "ROLLBACK_ELIGIBLE_AFTER_REVALIDATION")


def _noop():
    from contextlib import nullcontext
    return nullcontext()