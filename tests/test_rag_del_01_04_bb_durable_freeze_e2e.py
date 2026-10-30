"""RAG-DEL-01.04-BB: frozen supervisor -> real lab CAS -> rollback -> thaw.

Uses synthetic temp catalogs and mocks ONLY expensive isolated Qdrant/generation
proof providers. It never changes a real index, catalog or public pointer.
"""
import json
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from rag.runtime.knowledge_deletion_fenced_swap_lab import (
    laboratory_fenced_provenance_transition,
)
from rag.runtime.knowledge_deletion_reservation_freeze_lab import (
    freeze_deletion_reservations_lab, thaw_deletion_reservations_lab,
)
from rag.runtime.knowledge_deletion_supervisor_review import (
    inspect_deletion_supervisor_read_only,
)
from rag.runtime.knowledge_deletion_writer_fence_lab import (
    laboratory_writer_fence, DeletionWriterFenceBlocked,
)
from rag.runtime.knowledge_deletion_swap_lab import laboratory_rollback


class FrozenCatalogTransitionE2ETests(TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.queue = self.root / "auto" / "jobs" / "auto_index_jobs.sqlite3"
        self.queue.parent.mkdir(parents=True)
        with closing(sqlite3.connect(self.queue)) as db:
            db.execute("PRAGMA user_version=1")
            db.execute("CREATE TABLE auto_worker_lease "
                       "(singleton INTEGER PRIMARY KEY,job_id TEXT,lease_token TEXT,"
                       "lease_until_epoch REAL,generation INTEGER)")
            db.execute("INSERT INTO auto_worker_lease VALUES (1,NULL,NULL,NULL,2)")
            db.execute("CREATE TABLE auto_jobs (job_id TEXT,state TEXT)")
            db.commit()
        self.catalog = self.root / "project-indexes.json"
        self.pointer = self.root / "active-generation.json"
        self.catalog.write_text(json.dumps({
            "schema_version": 1, "projects": {
                "demo": {"project_id": "demo", "enabled": True,
                         "source_revision": "old", "generation_directory": "old"},
                "other": {"project_id": "other", "enabled": True,
                          "source_revision": "other", "generation_directory": "other"},
            },
        }), encoding="utf-8")
        self.pointer.write_text('{"schema_version":1,"generation":"public"}',
                                encoding="utf-8")
        self.baseline = self.catalog.read_bytes()
        self.public = self.pointer.read_bytes()
        self.candidate = {
            "index_family": "RAG_DEL_01", "project_id": "demo", "enabled": True,
            "source_revision": "new", "generation_directory": str(self.root / "candidate"),
            "source_directory": str(self.root / "snapshot"),
        }
        self.proof = {
            "state": "PRIVATE_REMOVAL_AUDIT_ONLY", "project_id": "demo",
            "lineage_sha256": "a" * 64,
            "snapshot_inventory_sha256": "b" * 64,
            "candidate_manifest_sha256": "c" * 64,
            "source_snapshot_files_verified": 2,
            "documents_verified": 2, "vectors_verified": 7,
            "activation_authorized": False, "catalog_modified": False,
        }
        self.freeze = freeze_deletion_reservations_lab(
            self.queue, laboratory_mode=True, operator_approved=True,
        )
        self.review = inspect_deletion_supervisor_read_only(self.queue)
        self.events = []

    def guard(self, name):
        @contextmanager
        def guard():
            self.events.append(name + "+")
            try:
                yield
            finally:
                self.events.append(name + "-")
        return guard

    def transition(self):
        return laboratory_fenced_provenance_transition(
            "demo", "old", self.candidate, {"project_id": "demo"},
            self.root / "baseline.json", object(),
            source_snapshot_root=self.root / "snapshot",
            queue_path=self.queue,
            reviewed_supervisor_evidence=self.review,
            generation_guard_factory=self.guard("generation"),
            semantic_guard_factory=self.guard("semantic"),
            catalog_file=self.catalog,
            public_pointer=self.pointer,
            laboratory_mode=True, operator_approved=True,
        )

    @patch("rag.runtime.knowledge_deletion_verified_swap_lab.verify_deletion_generation")
    @patch("rag.runtime.knowledge_deletion_provenance_swap_lab.audit_private_removal_candidate")
    def test_full_sequence_closed_provenance_swap_rollback_and_thaw(self, audit, verify):
        audit.return_value = self.proof
        result = self.transition()
        self.assertEqual(audit.call_count, 2)
        self.assertEqual(verify.call_count, 2)
        self.assertEqual(result["state"], "LAB_SWAP_ACTIVE")
        self.assertEqual(result["fence_state"], "LAB_WRITER_FENCE_HELD")
        self.assertFalse(result["activation_authorized"])
        self.assertFalse(result["operational_use_allowed"])
        self.assertEqual(json.loads(self.catalog.read_text())["projects"]["demo"],
                         self.candidate)
        self.assertEqual(json.loads(self.catalog.read_text())["projects"]["other"]
                         ["source_revision"], "other")
        self.assertEqual(self.pointer.read_bytes(), self.public)
        self.assertEqual(self.events,
                         ["generation+", "semantic+", "semantic-", "generation-"])
        with laboratory_writer_fence(
            self.queue, self.guard("generation"), self.guard("semantic"),
            laboratory_mode=True, operator_approved=True,
            expected_freeze_generation=self.review["reservation_freeze_generation"],
        ):
            back = laboratory_rollback(
                result["transaction"], catalog_file=self.catalog,
                public_pointer=self.pointer,
                operator_approved=True, laboratory_mode=True,
            )
        self.assertEqual(back["state"], "LAB_ROLLBACK_COMPLETE")
        self.assertEqual(self.catalog.read_bytes(), self.baseline)
        opened = thaw_deletion_reservations_lab(
            self.queue, self.freeze["freeze_token"], self.freeze["freeze_generation"],
            laboratory_mode=True, operator_approved=True,
        )
        self.assertEqual(opened["state"], "LAB_RESERVATIONS_OPEN")

    @patch("rag.runtime.knowledge_deletion_provenance_swap_lab.audit_private_removal_candidate")
    def test_stale_thaw_does_not_attempt_provenance_or_catalog(self, audit):
        thaw_deletion_reservations_lab(
            self.queue, self.freeze["freeze_token"], self.freeze["freeze_generation"],
            laboratory_mode=True, operator_approved=True,
        )
        with self.assertRaises(DeletionWriterFenceBlocked):
            self.transition()
        audit.assert_not_called()
        self.assertEqual(self.catalog.read_bytes(), self.baseline)
        self.assertEqual(self.pointer.read_bytes(), self.public)
        self.assertFalse(list(self.root.glob("rag-del-*.journal.json")))

    @patch("rag.runtime.knowledge_deletion_provenance_swap_lab.audit_private_removal_candidate")
    def test_job_queued_during_freeze_still_rejects_transition(self, audit):
        with closing(sqlite3.connect(self.queue)) as db:
            db.execute("INSERT INTO auto_jobs VALUES ('pending','QUEUED')")
            db.commit()
        with self.assertRaises(DeletionWriterFenceBlocked):
            self.transition()
        audit.assert_not_called()
        self.assertEqual(self.catalog.read_bytes(), self.baseline)
        self.assertFalse(list(self.root.glob("rag-del-*.journal.json")))