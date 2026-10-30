"""End-to-end temp-only CAS with second provenance audit under catalog lock."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from rag.runtime.knowledge_deletion_provenance_swap_lab import (
    laboratory_provenance_gated_swap, DeletionEvidenceGateError,
)
from rag.runtime.knowledge_deletion_swap_lab import laboratory_rollback


class LockedProvenanceE2ETests(TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
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
        self.row = {"project_id": "demo", "index_family": "RAG_DEL_01",
                    "enabled": True, "source_revision": "new",
                    "generation_directory": str(self.root / "candidate"),
                    "source_directory": str(self.root / "snapshot")}
        self.proof = {"state": "PRIVATE_REMOVAL_AUDIT_ONLY",
                      "project_id": "demo", "lineage_sha256": "a" * 64,
                      "snapshot_inventory_sha256": "b" * 64,
                      "candidate_manifest_sha256": "c" * 64,
                      "source_snapshot_files_verified": 2,
                      "documents_verified": 2, "vectors_verified": 7,
                      "activation_authorized": False, "catalog_modified": False}

    def swap(self):
        return laboratory_provenance_gated_swap(
            "demo", "old", self.row, {"project_id": "demo"},
            self.root / "baseline.json", object(),
            source_snapshot_root=self.root / "snapshots",
            catalog_file=self.catalog, public_pointer=self.pointer,
            laboratory_mode=True, operator_approved=True)

    @patch("rag.runtime.knowledge_deletion_verified_swap_lab.verify_deletion_generation")
    @patch("rag.runtime.knowledge_deletion_provenance_swap_lab.audit_private_removal_candidate")
    def test_changed_provenance_aborts_before_first_journal(self, audit, generation):
        audit.side_effect = [self.proof,
                             {**self.proof, "candidate_manifest_sha256": "d" * 64}]
        with self.assertRaises(DeletionEvidenceGateError):
            self.swap()
        self.assertEqual(generation.call_count, 2)
        self.assertEqual(audit.call_count, 2)
        self.assertEqual(self.catalog.read_bytes(), self.initial)
        self.assertEqual(self.pointer.read_bytes(), self.public)
        self.assertFalse(list(self.root.glob("rag-del-*.journal.json")))
        self.assertFalse(list(self.root.glob("rag-del-*.previous.json")))

    @patch("rag.runtime.knowledge_deletion_verified_swap_lab.verify_deletion_generation")
    @patch("rag.runtime.knowledge_deletion_provenance_swap_lab.audit_private_removal_candidate")
    def test_unchanged_provenance_preserves_other_and_rolls_back(self, audit, generation):
        audit.return_value = self.proof
        result = self.swap()
        self.assertEqual(audit.call_count, 2)
        self.assertEqual(generation.call_count, 2)
        self.assertEqual(result["state"], "LAB_SWAP_ACTIVE")
        self.assertFalse(result["operational_use_allowed"])
        self.assertEqual(self.pointer.read_bytes(), self.public)
        self.assertEqual(json.loads(self.catalog.read_text())["projects"]["other"]["source_revision"],
                         "other")
        back = laboratory_rollback(
            result["transaction"], catalog_file=self.catalog,
            public_pointer=self.pointer, operator_approved=True, laboratory_mode=True)
        self.assertEqual(back["state"], "LAB_ROLLBACK_COMPLETE")
        self.assertEqual(self.catalog.read_bytes(), self.initial)