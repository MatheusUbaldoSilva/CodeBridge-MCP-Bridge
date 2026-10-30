"""RAG-DEL-01.04-U: provenance adapter cannot bypass temp worker fencing."""
from contextlib import closing, contextmanager
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch

from rag.runtime.knowledge_deletion_fenced_swap_lab import (
    DeletionFencedTransitionError, laboratory_fenced_provenance_transition,
)
from rag.runtime.knowledge_deletion_writer_fence_lab import DeletionWriterFenceBlocked
from rag.runtime.knowledge_deletion_supervisor_review import inspect_deletion_supervisor_read_only


class FencedProvenanceAdapterTests(TestCase):
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
        self.cat = self.root / "project-indexes.json"
        self.pointer = self.root / "active-generation.json"
        self.cat.write_text('{"schema_version":1,"projects":{}}', encoding="utf-8")
        self.pointer.write_text('{"schema_version":1,"generation":"public"}',
                                encoding="utf-8")
        self.original = self.cat.read_bytes()
        self.public = self.pointer.read_bytes()
        self.row = {"project_id": "demo", "index_family": "RAG_DEL_01"}
        self.preview = {"project_id": "demo"}
        self.reviewed = inspect_deletion_supervisor_read_only(self.queue)
        self.events = []
        self.fake_swap = {
            "state": "LAB_SWAP_ACTIVE",
            "operational_use_allowed": False,
            "public_pointer_updated": False,
        }

    def guard(self, label):
        @contextmanager
        def lock():
            self.events.append(label + "+")
            try:
                yield
            finally:
                self.events.append(label + "-")
        return lock

    def transition(self, **kwargs):
        args = {
            "source_snapshot_root": self.root / "snapshot",
            "queue_path": self.queue,
            "reviewed_supervisor_evidence": self.reviewed,
            "generation_guard_factory": self.guard("generation"),
            "semantic_guard_factory": self.guard("semantic"),
            "catalog_file": self.cat,
            "public_pointer": self.pointer,
            "laboratory_mode": True,
            "operator_approved": True,
        }
        args.update(kwargs)
        return laboratory_fenced_provenance_transition(
            "demo", "old", self.row, self.preview,
            self.root / "baseline.json", Mock(), **args,
        )

    @patch("rag.runtime.knowledge_deletion_fenced_swap_lab.laboratory_provenance_gated_swap")
    def test_swap_call_occurs_only_inside_two_locks(self, swap):
        def witness(*args, **kwargs):
            self.assertEqual(self.events, ["generation+", "semantic+"])
            return self.fake_swap
        swap.side_effect = witness
        result = self.transition()
        self.assertEqual(result["fence_state"], "LAB_WRITER_FENCE_HELD")
        self.assertEqual(result["fence_lock_order"], ["queue", "generation", "semantic"])
        self.assertFalse(result["activation_authorized"])
        self.assertFalse(result["operational_use_allowed"])
        self.assertEqual(
            self.events, ["generation+", "semantic+", "semantic-", "generation-"]
        )
        swap.assert_called_once()

    @patch("rag.runtime.knowledge_deletion_fenced_swap_lab.laboratory_provenance_gated_swap")
    def test_pending_job_denies_swap(self, swap):
        with closing(sqlite3.connect(self.queue)) as db:
            db.execute("INSERT INTO auto_jobs VALUES ('one','RUNNING')")
            db.commit()
        with self.assertRaises(DeletionWriterFenceBlocked):
            self.transition()
        swap.assert_not_called()
        self.assertEqual(self.events, [])

    @patch("rag.runtime.knowledge_deletion_fenced_swap_lab.laboratory_provenance_gated_swap")
    def test_unapproved_transition_denied(self, swap):
        with self.assertRaises(PermissionError):
            self.transition(operator_approved=False)
        swap.assert_not_called()

    @patch("rag.runtime.knowledge_deletion_fenced_swap_lab.laboratory_provenance_gated_swap")
    def test_wrong_project_denied(self, swap):
        self.row = {"project_id": "foreign"}
        with self.assertRaises(DeletionFencedTransitionError):
            self.transition()
        swap.assert_not_called()

    @patch("rag.runtime.knowledge_deletion_fenced_swap_lab.laboratory_provenance_gated_swap")
    def test_untrusted_result_refused(self, swap):
        swap.return_value = {**self.fake_swap, "operational_use_allowed": True}
        with self.assertRaises(DeletionFencedTransitionError):
            self.transition()
        self.assertEqual(self.events[-2:], ["semantic-", "generation-"])

    @patch("rag.runtime.knowledge_deletion_fenced_swap_lab.laboratory_provenance_gated_swap")
    def test_underlying_failure_releases_both_guards(self, swap):
        swap.side_effect = ValueError("candidate receipt invalid")
        with self.assertRaises(ValueError):
            self.transition()
        self.assertEqual(self.events[-2:], ["semantic-", "generation-"])
        with closing(sqlite3.connect(self.queue, timeout=0.1)) as db:
            db.execute("BEGIN IMMEDIATE")
            db.rollback()
        self.assertEqual(self.cat.read_bytes(), self.original)
        self.assertEqual(self.pointer.read_bytes(), self.public)

    @patch("rag.runtime.knowledge_deletion_fenced_swap_lab.laboratory_provenance_gated_swap")
    def test_non_scratch_catalog_denied(self, swap):
        with self.assertRaises(Exception):
            self.transition(catalog_file=self.root.parent / "project-indexes.json")
        swap.assert_not_called()
    @patch("rag.runtime.knowledge_deletion_fenced_swap_lab.laboratory_provenance_gated_swap")
    def test_supervisor_generation_drift_requires_fresh_review(self, swap):
        with closing(sqlite3.connect(self.queue)) as db:
            # A worker may have reserved and released the singleton lease.
            db.execute("UPDATE auto_worker_lease SET generation=2")
            db.commit()
        with self.assertRaisesRegex(DeletionFencedTransitionError, "drift"):
            self.transition()
        swap.assert_not_called()
        self.assertEqual(self.events[-2:], ["semantic-", "generation-"])

    @patch("rag.runtime.knowledge_deletion_fenced_swap_lab.laboratory_provenance_gated_swap")
    def test_review_from_different_queue_is_rejected(self, swap):
        other = {**self.reviewed, "queue_identity_sha256": "f" * 64}
        with self.assertRaises(DeletionFencedTransitionError):
            self.transition(reviewed_supervisor_evidence=other)
        swap.assert_not_called()
        self.assertEqual(self.events, [])

    @patch("rag.runtime.knowledge_deletion_fenced_swap_lab.laboratory_provenance_gated_swap")
    def test_missing_review_fails_closed(self, swap):
        with self.assertRaises(DeletionFencedTransitionError):
            self.transition(reviewed_supervisor_evidence=None)
        swap.assert_not_called()

    @patch("rag.runtime.knowledge_deletion_fenced_swap_lab.laboratory_provenance_gated_swap")
    def test_forged_review_authorization_is_rejected(self, swap):
        forged = {**self.reviewed, "activation_authorized": True}
        with self.assertRaises(DeletionFencedTransitionError):
            self.transition(reviewed_supervisor_evidence=forged)
        swap.assert_not_called()

    @patch("rag.runtime.knowledge_deletion_fenced_swap_lab.laboratory_provenance_gated_swap")
    def test_bad_supervisor_generation_type_rejected(self, swap):
        forged = {**self.reviewed, "supervisor_generation": True}
        with self.assertRaises(DeletionFencedTransitionError):
            self.transition(reviewed_supervisor_evidence=forged)
        swap.assert_not_called()