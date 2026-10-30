"""RAG-DEL-01.04-Q: fence + catalog CAS integration, synthetic only."""
from contextlib import closing, contextmanager
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase

from rag.runtime.knowledge_deletion_writer_fence_lab import laboratory_writer_fence
from rag.runtime.knowledge_deletion_swap_lab import (
    DeletionSwapError, laboratory_rollback, laboratory_swap,
)


class FencedSwapIntegrationTests(TestCase):
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
            db.execute("INSERT INTO auto_worker_lease VALUES (1,NULL,NULL,NULL,3)")
            db.execute("CREATE TABLE auto_jobs (job_id TEXT,state TEXT)")
            db.execute("PRAGMA user_version=1")
            db.commit()
        self.catalog = self.root / "project-indexes.json"
        self.pointer = self.root / "active-generation.json"
        self.catalog.write_text(json.dumps({"schema_version": 1, "projects": {
            "demo": {"project_id": "demo", "enabled": True,
                     "source_revision": "old", "generation_directory": "old"},
            "other": {"project_id": "other", "enabled": True,
                      "source_revision": "other", "generation_directory": "other"},
        }}), encoding="utf-8")
        self.pointer.write_text('{"schema_version":1,"generation":"public"}',
                                encoding="utf-8")
        self.initial = self.catalog.read_bytes()
        self.public = self.pointer.read_bytes()
        self.candidate = {"project_id": "demo", "enabled": True,
                          "source_revision": "new", "generation_directory": "new"}
        self.acquired = []

    def guard(self, name):
        @contextmanager
        def hold():
            self.acquired.append(name + "+")
            try:
                yield
            finally:
                self.acquired.append(name + "-")
        return hold

    def fence(self):
        return laboratory_writer_fence(
            self.queue, self.guard("generation"), self.guard("semantic"),
            laboratory_mode=True, operator_approved=True,
        )

    def swap(self, *, fail_at=None):
        return laboratory_swap(
            "demo", "old", self.candidate,
            catalog_file=self.catalog, public_pointer=self.pointer,
            operator_approved=True, laboratory_mode=True, _fail_at=fail_at,
        )

    def test_catalog_swap_and_rollback_under_queue_barrier(self):
        with self.fence() as evidence:
            self.assertFalse(evidence["operational_use_allowed"])
            r = self.swap()
            row = json.loads(self.catalog.read_text())["projects"]
            self.assertEqual(row["demo"]["source_revision"], "new")
            self.assertEqual(row["other"]["source_revision"], "other")
            self.assertEqual(self.pointer.read_bytes(), self.public)
            self.assertEqual(
                laboratory_rollback(r["transaction"], catalog_file=self.catalog,
                                    public_pointer=self.pointer,
                                    operator_approved=True, laboratory_mode=True)["state"],
                "LAB_ROLLBACK_COMPLETE",
            )
        self.assertEqual(self.catalog.read_bytes(), self.initial)
        self.assertEqual(
            self.acquired,
            ["generation+", "semantic+", "semantic-", "generation-"],
        )

    def test_interrupted_catalog_swap_releases_queue_and_locks(self):
        with self.assertRaises(DeletionSwapError):
            with self.fence():
                self.swap(fail_at="after")
        self.assertEqual(self.acquired[-2:], ["semantic-", "generation-"])
        with closing(sqlite3.connect(self.queue, timeout=0.1)) as db:
            db.execute("BEGIN IMMEDIATE")
            db.rollback()
        # Reconciliation is explicitly separate from the failed transaction.
        journal = next(self.root.glob("rag-del-*.journal.json"))
        transaction = journal.name[len("rag-del-"):-len(".journal.json")]
        self.assertEqual(
            laboratory_rollback(transaction, catalog_file=self.catalog,
                                public_pointer=self.pointer,
                                operator_approved=True, laboratory_mode=True)["state"],
            "LAB_ROLLBACK_COMPLETE",
        )
        self.assertEqual(self.catalog.read_bytes(), self.initial)

    def test_runnable_queue_never_reaches_catalog(self):
        with closing(sqlite3.connect(self.queue)) as db:
            db.execute("INSERT INTO auto_jobs VALUES ('worker-1','RUNNING')")
            db.commit()
        with self.assertRaises(Exception):
            with self.fence():
                self.swap()
        self.assertEqual(self.catalog.read_bytes(), self.initial)
        self.assertFalse(list(self.root.glob("rag-del-*.journal.json")))
        self.assertEqual(self.acquired, [])