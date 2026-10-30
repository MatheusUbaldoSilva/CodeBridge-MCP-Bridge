"""RAG-DEL-01.04-Y: durable scratch freeze against the real AUTO reservation API."""
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
import sqlite3
import subprocess
import sys

from rag.runtime.auto_index_queue import create_draft
from rag.runtime.auto_index_approval import (
    build_auto_index_preview, approve_auto_index_draft,
)
from rag.runtime.auto_index_supervisor import (
    reserve_index_supervisor, release_index_supervisor,
)
from rag.runtime.knowledge_deletion_reservation_freeze_lab import (
    DeletionReservationFreezeError,
    freeze_deletion_reservations_lab, thaw_deletion_reservations_lab,
    _read_marker_locked,
)


class DurableReservationFreezeTests(TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.queue = self.root / "auto" / "jobs" / "auto_index_jobs.sqlite3"
        self.source = self.root / "source"
        self.source.mkdir()
        (self.source / "main.py").write_text("print('test')", encoding="utf-8")
        self.job = create_draft(
            self.queue, project_id="demo", source_root=self.source,
            idempotency_key="durable-freeze-lab-req-1", allow_write=True,
        )
        preview = build_auto_index_preview("demo", self.source)
        approve_auto_index_draft(
            self.queue, self.job["job_id"], preview,
            confirmed_digest=preview["review_sha256"],
            operator_approved=True, allow_write=True,
        )
        reserved = self.reserve()
        released = release_index_supervisor(
            self.queue, self.job["job_id"],
            reserved["lease_token"], reserved["generation"],
        )
        self.assertTrue(released["accepted"])

    def reserve(self):
        return reserve_index_supervisor(
            self.queue, self.job["job_id"],
            operator_approved=True, reservation_enabled=True,
        )

    def freeze(self):
        return freeze_deletion_reservations_lab(
            self.queue, laboratory_mode=True, operator_approved=True,
        )

    def thaw(self, freeze):
        return thaw_deletion_reservations_lab(
            self.queue, freeze["freeze_token"], freeze["freeze_generation"],
            laboratory_mode=True, operator_approved=True,
        )

    def read(self):
        with closing(sqlite3.connect(self.queue)) as db:
            return _read_marker_locked(db)

    def test_freeze_denies_central_reservation_and_survives_connection_restart(self):
        freeze = self.freeze()
        self.assertTrue(freeze["durable_marker"])
        self.assertFalse(freeze["workers_stopped"])
        with self.assertRaises(DeletionReservationFreezeError):
            self.reserve()
        self.assertEqual(self.read()["token"], freeze["freeze_token"])
        child = subprocess.run(
            [sys.executable, "-c", r"""
from pathlib import Path
import sys
from rag.runtime.auto_index_supervisor import reserve_index_supervisor
reserve_index_supervisor(Path(sys.argv[1]),sys.argv[2],
                         operator_approved=True,reservation_enabled=True)
""", str(self.queue), self.job["job_id"]],
            capture_output=True, text=True, timeout=8,
            cwd=str(Path(__file__).resolve().parents[1]),
        )
        self.assertNotEqual(child.returncode, 0)
        self.assertIn("DeletionReservationFreezeError", child.stderr)
        self.assertEqual(self.thaw(freeze)["state"], "LAB_RESERVATIONS_OPEN")
        self.assertEqual(self.reserve()["state"], "RESERVED_NO_WORKER")

    def test_stale_or_foreign_thaw_is_refused(self):
        freeze = self.freeze()
        with self.assertRaises(DeletionReservationFreezeError):
            thaw_deletion_reservations_lab(
                self.queue, "0" * 32, freeze["freeze_generation"],
                laboratory_mode=True, operator_approved=True,
            )
        with self.assertRaises(DeletionReservationFreezeError):
            thaw_deletion_reservations_lab(
                self.queue, freeze["freeze_token"],
                freeze["freeze_generation"] + 1,
                laboratory_mode=True, operator_approved=True,
            )
        self.assertEqual(self.read()["state"], "FROZEN")

    def test_double_freeze_denied_and_epoch_changes_on_reopen(self):
        a = self.freeze()
        with self.assertRaisesRegex(DeletionReservationFreezeError, "already"):
            self.freeze()
        self.thaw(a)
        b = self.freeze()
        self.assertEqual(b["freeze_generation"], a["freeze_generation"] + 2)
        self.assertNotEqual(a["freeze_token"], b["freeze_token"])
        with self.assertRaises(DeletionReservationFreezeError):
            self.thaw(a)
        self.thaw(b)

    def test_freeze_does_not_clear_existing_active_lease(self):
        active = self.reserve()
        freeze = self.freeze()
        self.assertFalse(freeze["workers_stopped"])
        with closing(sqlite3.connect(self.queue)) as db:
            row = db.execute(
                "SELECT job_id FROM auto_worker_lease WHERE singleton=1"
            ).fetchone()
            self.assertEqual(row[0], self.job["job_id"])
        self.assertRaises(DeletionReservationFreezeError, self.reserve)
        self.thaw(freeze)
        release_index_supervisor(
            self.queue, self.job["job_id"], active["lease_token"],
            active["generation"],
        )

    def test_laboratory_path_cannot_target_real_queue(self):
        other = self.root / "untrusted" / "auto" / "jobs"
        other.mkdir(parents=True)
        outside = other / "auto_index_jobs.sqlite3"
        outside.write_bytes(self.queue.read_bytes())
        with self.assertRaises(DeletionReservationFreezeError):
            freeze_deletion_reservations_lab(
                outside, laboratory_mode=True, operator_approved=True,
            )

    def test_no_approval_does_not_write_freeze_marker(self):
        for mode, approved in ((False, True), (True, False)):
            with self.assertRaises(PermissionError):
                freeze_deletion_reservations_lab(
                    self.queue, laboratory_mode=mode, operator_approved=approved,
                )
        self.assertIsNone(self.read())

    def test_malformed_marker_denies_reservation(self):
        freeze = self.freeze()
        with closing(sqlite3.connect(self.queue)) as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute(
                    "UPDATE auto_deletion_reservation_freeze "
                    "SET generation=0 WHERE singleton=1"
                )
            db.rollback()
        # A corrupt shape is refused even if a rogue process rebuilt its table.
        with closing(sqlite3.connect(self.queue)) as db:
            db.execute("DROP TABLE auto_deletion_reservation_freeze")
            db.execute("CREATE TABLE auto_deletion_reservation_freeze (broken TEXT)")
            db.commit()
        with self.assertRaises(DeletionReservationFreezeError):
            self.reserve()

    def test_missing_marker_row_fails_closed(self):
        self.freeze()
        with closing(sqlite3.connect(self.queue)) as db:
            db.execute("DELETE FROM auto_deletion_reservation_freeze")
            db.commit()
        with self.assertRaises(DeletionReservationFreezeError):
            self.reserve()

    def test_lab_freeze_never_modifies_public_catalog(self):
        private = self.root / "project-indexes.json"
        pointer = self.root / "active-generation.json"
        private.write_bytes(b"private-stub")
        pointer.write_bytes(b"public-stub")
        freeze = self.freeze()
        self.thaw(freeze)
        self.assertEqual(private.read_bytes(), b"private-stub")
        self.assertEqual(pointer.read_bytes(), b"public-stub")

    def test_freeze_transaction_is_durable_after_process_termination(self):
        process = subprocess.run(
            [sys.executable, "-c", r"""
import os,sys
from pathlib import Path
from rag.runtime.knowledge_deletion_reservation_freeze_lab import freeze_deletion_reservations_lab
freeze_deletion_reservations_lab(Path(sys.argv[1]),
                                laboratory_mode=True,operator_approved=True)
os._exit(27)
""", str(self.queue)],
            capture_output=True, text=True, timeout=8,
            cwd=str(Path(__file__).resolve().parents[1]),
        )
        self.assertEqual(process.returncode, 27, process.stderr)
        self.assertEqual(self.read()["state"], "FROZEN")
        with self.assertRaises(DeletionReservationFreezeError):
            self.reserve()