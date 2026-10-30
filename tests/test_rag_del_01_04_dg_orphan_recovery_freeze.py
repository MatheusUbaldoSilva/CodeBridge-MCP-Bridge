"""RAG-DEL-01.04-DG: real scratch AUTO orphan recovery under durable freeze."""
from contextlib import closing, nullcontext
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
import sqlite3

from rag.runtime.auto_index_queue import (
    create_draft, get_job, AutoIndexQueueError,
)
from rag.runtime.auto_index_approval import (
    build_auto_index_preview, approve_auto_index_draft,
)
from rag.runtime.auto_index_staging import prepare_auto_staging
from rag.runtime.auto_index_supervisor import reserve_index_supervisor
from rag.runtime.auto_index_checkpoint import recover_orphaned_auto_job
from rag.runtime.knowledge_deletion_reservation_freeze_lab import (
    freeze_deletion_reservations_lab,
    thaw_deletion_reservations_lab,
    DeletionReservationFreezeError,
)
from rag.runtime.knowledge_deletion_supervisor_review import (
    inspect_deletion_supervisor_read_only,
)


class OrphanFreezeLifecycleTests(TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        (self.source / "README.md").write_text(
            "Synthetic recovery under frozen queue\n", encoding="utf-8",
        )
        self.queue = self.root / "auto" / "jobs" / "auto_index_jobs.sqlite3"
        draft = create_draft(
            self.queue, project_id="orphan-lab", source_root=self.source,
            idempotency_key="orphan-freeze-lab-1234", allow_write=True,
        )
        self.job = draft["job_id"]
        preview = build_auto_index_preview("orphan-lab", self.source)
        approve_auto_index_draft(
            self.queue, self.job, preview,
            confirmed_digest=preview["review_sha256"],
            operator_approved=True, allow_write=True,
        )
        prepare_auto_staging(
            self.queue, self.job,
            operator_approved=True, preparation_enabled=True,
        )
        self.owner = reserve_index_supervisor(
            self.queue, self.job,
            operator_approved=True, reservation_enabled=True,
            lease_seconds=30, now_epoch=100,
        )
        with closing(sqlite3.connect(self.queue)) as db:
            db.execute(
                "UPDATE auto_jobs SET state='RUNNING' WHERE job_id=?",
                (self.job,),
            )
            db.commit()
        self.freeze = freeze_deletion_reservations_lab(
            self.queue, laboratory_mode=True, operator_approved=True,
        )

    def review(self, epoch):
        return inspect_deletion_supervisor_read_only(
            self.queue, now_epoch=epoch,
        )

    def test_expired_job_requeues_but_freeze_still_blocks_new_reserve(self):
        before = self.review(131)
        self.assertEqual(
            before["lease_status"], "EXPIRED_RECONCILIATION_REQUIRED",
        )
        self.assertIn("UNRESOLVED_QUEUE_JOBS", before["blockers"])
        self.assertTrue(before["reservation_freeze_active"])
        self.assertFalse(before["activation_authorized"])
        recovered = recover_orphaned_auto_job(
            self.queue, self.job,
            operator_approved=True, now_epoch=131,
            semantic_guard_factory=nullcontext,
        )
        self.assertEqual(recovered["state"], "QUEUED")
        self.assertEqual(get_job(self.queue, self.job)["state"], "QUEUED")
        current = self.review(132)
        self.assertEqual(current["lease_status"], "NONE")
        self.assertIn("UNRESOLVED_QUEUE_JOBS", current["blockers"])
        self.assertTrue(current["reservation_freeze_active"])
        with self.assertRaises(DeletionReservationFreezeError):
            reserve_index_supervisor(
                self.queue, self.job,
                operator_approved=True, reservation_enabled=True,
            )
        self.assertFalse(current["activation_authorized"])
        self.assertEqual(
            thaw_deletion_reservations_lab(
                self.queue, self.freeze["freeze_token"],
                self.freeze["freeze_generation"],
                laboratory_mode=True, operator_approved=True,
            )["state"], "LAB_RESERVATIONS_OPEN",
        )
        next_reserve = reserve_index_supervisor(
            self.queue, self.job,
            operator_approved=True, reservation_enabled=True,
        )
        self.assertEqual(next_reserve["state"], "RESERVED_NO_WORKER")
        self.assertGreater(next_reserve["generation"], self.owner["generation"])

    def test_nonexpired_lease_cannot_be_forced_to_recover(self):
        before = self.review(129)
        self.assertEqual(before["lease_status"], "ACTIVE")
        with self.assertRaises(AutoIndexQueueError):
            recover_orphaned_auto_job(
                self.queue, self.job,
                operator_approved=True, now_epoch=129,
                semantic_guard_factory=nullcontext,
            )
        self.assertEqual(get_job(self.queue, self.job)["state"], "RUNNING")
        after = self.review(129)
        self.assertTrue(after["reservation_freeze_active"])
        self.assertFalse(after["activation_authorized"])
        self.assertEqual(after["lease_status"], "ACTIVE")

    def test_unapproved_recovery_never_modifies_lease_or_job(self):
        before = self.review(131)
        with self.assertRaises(PermissionError):
            recover_orphaned_auto_job(
                self.queue, self.job, now_epoch=131,
                semantic_guard_factory=nullcontext,
            )
        after = self.review(131)
        self.assertEqual(after["supervisor_generation"],
                         before["supervisor_generation"])
        self.assertEqual(after["lease_status"], before["lease_status"])
        self.assertEqual(get_job(self.queue, self.job)["state"], "RUNNING")