"""Reject corrupt terminal deletion journals before any new lab transaction."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from rag.runtime.knowledge_deletion_swap_lab import (
    DeletionSwapError, _journal_payload, laboratory_rollback, laboratory_swap,
)


class TerminalJournalGuardTests(TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.catalog = self.root / "project-indexes.json"
        self.pointer = self.root / "active-generation.json"
        self.catalog.write_text(json.dumps({"schema_version": 1, "projects": {
            "demo": {"project_id": "demo", "enabled": True,
                     "source_revision": "old", "generation_directory": "old"},
        }}), encoding="utf-8")
        self.pointer.write_text('{"schema_version":1,"generation":"public"}', encoding="utf-8")
        self.candidate = {"project_id": "demo", "enabled": True,
                          "source_revision": "new", "generation_directory": "new"}
        original = self.catalog.read_bytes()
        result = self.swap()
        laboratory_rollback(result["transaction"], catalog_file=self.catalog,
                            public_pointer=self.pointer,
                            operator_approved=True, laboratory_mode=True)
        self.assertEqual(self.catalog.read_bytes(), original)
        self.journal = self.root / ("rag-del-" + result["transaction"] + ".journal.json")
        self.backup = self.root / ("rag-del-" + result["transaction"] + ".previous.json")
        self.original_pointer = self.pointer.read_bytes()

    def swap(self):
        return laboratory_swap("demo", "old", self.candidate,
                               catalog_file=self.catalog, public_pointer=self.pointer,
                               operator_approved=True, laboratory_mode=True)

    def assert_rejected_without_side_effect(self):
        before = self.catalog.read_bytes()
        with self.assertRaises(DeletionSwapError):
            self.swap()
        self.assertEqual(self.catalog.read_bytes(), before)
        self.assertEqual(self.pointer.read_bytes(), self.original_pointer)
        self.assertEqual(len(list(self.root.glob("rag-del-*.journal.json"))), 1)

    def resign(self, **changes):
        record = json.loads(self.journal.read_text(encoding="utf-8"))
        record.update(changes)
        self.journal.write_bytes(_journal_payload(record))

    def test_valid_rolled_back_journal_permits_new_lab_swap(self):
        self.assertEqual(self.swap()["state"], "LAB_SWAP_ACTIVE")

    def test_tampered_backup_blocks_next_swap(self):
        self.backup.write_bytes(b"not-original")
        self.assert_rejected_without_side_effect()

    def test_missing_backup_blocks_next_swap(self):
        self.backup.unlink()
        self.assert_rejected_without_side_effect()

    def test_signed_wrong_transaction_blocks_next_swap(self):
        self.resign(transaction="0" * 32)
        self.assert_rejected_without_side_effect()

    def test_signed_wrong_backup_path_blocks_next_swap(self):
        self.resign(backup=str(self.root / "elsewhere.json"))
        self.assert_rejected_without_side_effect()

    def test_signed_invalid_state_blocks_next_swap(self):
        self.resign(state="ROLLED_BACK_BUT_FAKE")
        self.assert_rejected_without_side_effect()

    def test_signed_invalid_schema_blocks_next_swap(self):
        self.resign(schema_version=99)
        self.assert_rejected_without_side_effect()