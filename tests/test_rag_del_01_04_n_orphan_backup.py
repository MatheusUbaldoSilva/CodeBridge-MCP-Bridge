"""Fail-closed discovery of backup created before a deletion journal."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from rag.runtime.knowledge_deletion_preflight import (
    PrivateDeletionPreflightError, inspect_private_deletion_preflight,
)
from rag.runtime.knowledge_deletion_swap_lab import DeletionSwapError, laboratory_swap


class OrphanDeletionBackupTests(TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.catalog = self.root / "project-indexes.json"
        self.pointer = self.root / "active-generation.json"
        self.catalog.write_text(json.dumps({"schema_version": 1, "projects": {
            "demo": {"project_id": "demo", "enabled": True,
                     "source_revision": "old", "generation_directory": "old"}
        }}), encoding="utf-8")
        self.pointer.write_text('{"schema_version":1,"generation":"public"}',
                                encoding="utf-8")
        self.candidate = {"project_id": "demo", "enabled": True,
                          "index_family": "RAG_DEL_01", "source_revision": "new",
                          "generation_directory": "new"}
        self.original = self.catalog.read_bytes()
        self.public = self.pointer.read_bytes()

    def preflight(self):
        return inspect_private_deletion_preflight(
            self.catalog, self.pointer, "demo", "old", self.candidate)

    def swap(self):
        return laboratory_swap(
            "demo", "old", self.candidate,
            catalog_file=self.catalog, public_pointer=self.pointer,
            operator_approved=True, laboratory_mode=True)

    def assert_rejects_orphan(self):
        with self.assertRaises(PrivateDeletionPreflightError):
            self.preflight()
        with self.assertRaises(DeletionSwapError):
            self.swap()
        self.assertEqual(self.catalog.read_bytes(), self.original)
        self.assertEqual(self.pointer.read_bytes(), self.public)
        self.assertFalse(list(self.root.glob("rag-del-*.journal.json")))

    def test_valid_catalog_preflight_without_backup(self):
        self.assertFalse(self.preflight()["activation_authorized"])
        self.assertEqual(self.catalog.read_bytes(), self.original)

    def test_backup_without_journal_is_fail_closed(self):
        orphan = self.root / ("rag-del-" + "a" * 32 + ".previous.json")
        orphan.write_bytes(self.original)
        self.assert_rejects_orphan()

    def test_invalid_transaction_name_is_fail_closed(self):
        orphan = self.root / "rag-del-malformed.previous.json"
        orphan.write_bytes(self.original)
        self.assert_rejects_orphan()