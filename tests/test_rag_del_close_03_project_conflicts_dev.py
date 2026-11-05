"""Disposable read-only project-scoped conflict inventory tests."""
from __future__ import annotations

from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from rag.runtime.knowledge_deletion_project_conflicts_dev import (
    inspect_project_conflicts_read_only,
)


def write_json(path, data):
    path.write_text(json.dumps(data,sort_keys=True),encoding="utf-8")


class ProjectConflictsDevTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name).resolve()
        self.catalog_root=self.root/"rag"
        self.catalog_root.mkdir()
        self.queue=self.root/"queue.sqlite3"
        self.one=self.root/"one"
        self.two=self.root/"two"
        self.one.mkdir()
        self.two.mkdir()
        self.job="d"*32
        self.catalog=self.catalog_root/"project-indexes.json"
        self.pointer=self.catalog_root/"active-generation.json"
        self.projects={
            "privateone":dict(enabled=True,generation_directory=str(self.one)),
            "privatetwo":dict(enabled=True,generation_directory=str(self.two),
                              job_id=self.job),
        }
        write_json(self.catalog,dict(schema_version=1,projects=self.projects))
        write_json(self.pointer,dict(schema_version=1,generation="public-base"))
        with closing(sqlite3.connect(self.queue)) as con:
            con.execute("PRAGMA user_version=1")
            con.execute("CREATE TABLE auto_jobs (job_id TEXT, project_id TEXT, state TEXT)")
            con.execute("INSERT INTO auto_jobs VALUES (?,?,?)",
                        (self.job,"privatetwo","READY_FOR_REVIEW"))
            con.commit()
        self.backup=self.catalog_root/f"auto-canary-{self.job}.previous.json"
        self.backup.write_bytes(b"previous catalog bytes")
        self.journal=self.catalog_root/f"auto-canary-{self.job}.journal.json"
        self._write_canary()

    def _write_canary(self,**kwargs):
        data=dict(
            schema_version=1,state="CANARY_ACTIVE",job_id=self.job,
            project_id="privatetwo",catalog=str(self.catalog),
            new_sha256=hashlib.sha256(self.catalog.read_bytes()).hexdigest(),
            public_pointer_sha256=hashlib.sha256(self.pointer.read_bytes()).hexdigest(),
            backup=str(self.backup),
            old_sha256=hashlib.sha256(self.backup.read_bytes()).hexdigest()
        )
        data.update(kwargs)
        write_json(self.journal,data)

    def _review(self,project="privateone"):
        return inspect_project_conflicts_read_only(
            project_id=project,catalog_directory=self.catalog_root,
            queue_path=self.queue)

    def test_unrelated_canary_allows_planning_never_activation(self):
        files=(self.catalog,self.pointer,self.queue,self.journal,self.backup)
        before=[hashlib.sha256(p.read_bytes()).hexdigest() for p in files]
        report=self._review()
        after=[hashlib.sha256(p.read_bytes()).hexdigest() for p in files]
        self.assertEqual(before,after)
        self.assertEqual(report["state"],"TARGET_CONFLICTS_CLEAR_FOR_READONLY_PLANNING")
        self.assertTrue(report["target_isolation_proven"])
        self.assertEqual(report["target_queue_jobs"],0)
        self.assertEqual(report["target_active_canaries"],0)
        self.assertEqual(report["unrelated_queue_jobs"],1)
        self.assertEqual(report["unrelated_active_canaries"],1)
        self.assertTrue(report["catalog_cas_required"])
        self.assertFalse(report["activation_authorized"])
        self.assertFalse(report["operational_use_allowed"])

    def test_target_private_project_canary_blocks(self):
        report=self._review("privatetwo")
        self.assertFalse(report["target_isolation_proven"])
        self.assertIn("TARGET_CANARY_ACTIVE",report["blockers"])
        self.assertIn("TARGET_QUEUE_JOB_ACTIVE",report["blockers"])

    def test_mutated_pointer_since_canary_blocks(self):
        write_json(self.pointer,dict(schema_version=1,generation="changed"))
        report=self._review()
        self.assertIn("PROJECT_CONFLICT_INVENTORY_UNVERIFIED",report["blockers"])
        self.assertFalse(report["target_isolation_proven"])

    def test_tampered_rollback_backup_blocks(self):
        self.backup.write_bytes(b"tampered rollback")
        report=self._review()
        self.assertIn("PROJECT_CONFLICT_INVENTORY_UNVERIFIED",report["blockers"])

    def test_same_or_nested_generation_directories_block(self):
        self.projects["privatetwo"]["generation_directory"]=str(self.one)
        write_json(self.catalog,dict(schema_version=1,projects=self.projects))
        self._write_canary()
        report=self._review()
        self.assertIn("GENERATION_DIRECTORIES_OVERLAP",report["blockers"])

    def test_missing_private_project_does_not_create_it(self):
        report=self._review("not-present")
        self.assertIn("TARGET_NOT_PRESENT_IN_PRIVATE_CATALOG",report["blockers"])
        self.assertFalse(report["activation_authorized"])

    def test_untrusted_queue_missing_is_denied(self):
        self.queue.unlink()
        report=self._review()
        self.assertIn("UNTRUSTED_STORAGE",report["blockers"])
