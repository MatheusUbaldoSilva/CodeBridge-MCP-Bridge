"""Isolated tests for read-only operational queue/canary reconciliation."""
from __future__ import annotations

from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from rag.runtime.knowledge_deletion_operational_reconcile_dev import (
    reconcile_operational_generation_read_only,
)


def _dump(path: Path, obj: dict):
    path.write_text(json.dumps(obj, sort_keys=True), encoding="utf-8")


class OperationalReconcileDevTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.catalog = root / "catalog"
        self.catalog.mkdir()
        self.queue = root / "auto" / "jobs" / "auto_index_jobs.sqlite3"
        self.queue.parent.mkdir(parents=True)
        self.candidate = root / "candidate"
        self.candidate.mkdir()
        self.generation = root / "generation"
        self.generation.mkdir()
        self.job = "a" * 32
        self.project = "testprivate"
        _dump(self.catalog / "active-generation.json",
              {"schema_version": 1, "generation": "public-v1"})
        self.project_file = self.catalog / "project-indexes.json"
        _dump(self.project_file, {"schema_version": 1, "projects": {
            self.project: {
                "job_id": self.job,
                "generation_directory": str(self.generation)
            }
        }})
        with closing(sqlite3.connect(self.queue)) as db:
            db.execute("PRAGMA user_version=1")
            db.execute("CREATE TABLE auto_jobs (job_id TEXT, project_id TEXT,"
                       "state TEXT, approved INTEGER, candidate_generation TEXT)")
            db.commit()

    def _insert_pending(self):
        with closing(sqlite3.connect(self.queue)) as db:
            db.execute("INSERT INTO auto_jobs VALUES (?,?,?,?,?)",
                       (self.job,self.project,"READY_FOR_REVIEW",1,
                        str(self.candidate)))
            db.commit()

    def _canary(self):
        backup = self.catalog / f"auto-canary-{self.job}.previous.json"
        backup.write_bytes(b"before-canary")
        record = {
            "job_id": self.job,
            "project_id": self.project,
            "state": "CANARY_ACTIVE",
            "schema_version": 1,
            "public_pointer_sha256": hashlib.sha256((self.catalog/"active-generation.json").read_bytes()).hexdigest(),
            "catalog": str(self.project_file),
            "backup": str(backup),
            "new_sha256": hashlib.sha256(self.project_file.read_bytes()).hexdigest(),
            "old_sha256": hashlib.sha256(backup.read_bytes()).hexdigest(),
        }
        _dump(self.catalog / f"auto-canary-{self.job}.journal.json", record)
        return backup

    def _review(self):
        return reconcile_operational_generation_read_only(
            self.catalog.resolve(), self.queue
        )

    def test_quiet_queue_still_never_authorizes_deletion(self):
        result = self._review()
        self.assertEqual(result["state"],
                         "CLOSE03_READONLY_QUEUE_CANARY_QUIET_UNTRUSTED_IPC")
        self.assertEqual(result["queue_pending_count"], 0)
        self.assertEqual(result["canary_count"], 0)
        self.assertFalse(result["activation_authorized"])
        self.assertFalse(result["operational_use_allowed"])
        self.assertFalse(result["ready_for_operational_pilot"])

    def test_pending_and_active_canary_are_consistent_but_blocked(self):
        self._insert_pending()
        self._canary()
        tracked = [self.queue, self.project_file,
                   self.catalog / f"auto-canary-{self.job}.journal.json"]
        before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked]
        result = self._review()
        after = [hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked]
        self.assertEqual(before,after)
        self.assertTrue(result["canary_catalog_consistent"])
        self.assertTrue(result["canary_rollback_preflight_consistent"])
        self.assertTrue(result["matched_canary_queue_job"])
        self.assertEqual(result["queue_pending_count"],1)
        self.assertIn("QUEUE_PENDING_OPERATOR_REVIEW_REQUIRED",result["blockers"])
        self.assertIn("ACTIVE_CANARY_OPERATOR_REVIEW_REQUIRED",result["blockers"])
        self.assertFalse(result["activation_authorized"])

    def test_public_pointer_changed_after_canary_blocks_preflight(self):
        self._insert_pending()
        self._canary()
        _dump(self.catalog / "active-generation.json",
              {"schema_version": 1, "generation": "unapproved-new-generation"})
        result = self._review()
        self.assertFalse(result["canary_rollback_preflight_consistent"])
        self.assertIn("CANARY_CATALOG_INCONSISTENT", result["blockers"])
        self.assertFalse(result["activation_authorized"])

    def test_tampered_canary_backup_fails_closed(self):
        self._insert_pending()
        self._canary().write_bytes(b"tampered")
        result = self._review()
        self.assertFalse(result["canary_catalog_consistent"])
        self.assertIn("CANARY_CATALOG_INCONSISTENT",result["blockers"])
        self.assertFalse(result["activation_authorized"])

    def test_changed_queue_receipt_with_same_count_fails_closed(self):
        self._insert_pending()
        fake = {
            "state": "AUTO_REVIEW_JOBS_BLOCKED_READ_ONLY",
            "blockers": ["PENDING_REVIEW_JOBS_PRESENT"],
            "pending_jobs": [{
                "job_sha256": "0" * 64, "project_sha256": "0" * 64,
                "state": "READY_FOR_REVIEW", "approved": True,
                "has_candidate": True
            }],
        }
        with patch(
            "rag.runtime.knowledge_deletion_operational_reconcile_dev."
            "inspect_pending_review_jobs_dev", return_value=fake
        ):
            result = self._review()
        self.assertIn("OPERATIONAL_EVIDENCE_UNVERIFIED", result["blockers"])
        self.assertFalse(result["activation_authorized"])
    def test_oversized_backup_fails_closed(self):
        self._insert_pending()
        backup = self._canary()
        backup.write_bytes(b"x" * (1048576 + 1))
        result = self._review()
        self.assertIn("CANARY_CATALOG_INCONSISTENT", result["blockers"])
        self.assertFalse(result["activation_authorized"])
    def test_missing_queue_is_blocked_without_creation(self):
        self.queue.unlink()
        result = self._review()
        self.assertFalse(self.queue.exists())
        self.assertIn("QUEUE_READ_UNVERIFIED",result["blockers"])
        self.assertFalse(result["operational_use_allowed"])


if __name__ == "__main__":
    unittest.main()
