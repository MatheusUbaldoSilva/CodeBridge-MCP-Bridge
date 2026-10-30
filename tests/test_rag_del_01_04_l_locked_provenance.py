"""Provenance must be checked again inside the lab catalog critical section."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch

from rag.runtime.knowledge_deletion_provenance_swap_lab import (
    laboratory_provenance_gated_swap, DeletionEvidenceGateError,
)


class LockedProvenanceTests(TestCase):
    def setUp(self):
        t = TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        self.candidate = {"project_id": "demo", "index_family": "RAG_DEL_01",
                          "generation_directory": str(self.root / "candidate")}
        self.proof = {"state": "PRIVATE_REMOVAL_AUDIT_ONLY",
                      "project_id": "demo", "lineage_sha256": "a" * 64,
                      "snapshot_inventory_sha256": "b" * 64,
                      "candidate_manifest_sha256": "c" * 64,
                      "source_snapshot_files_verified": 2,
                      "documents_verified": 2, "vectors_verified": 7,
                      "activation_authorized": False, "catalog_modified": False}
        self.args = dict(catalog_file=self.root / "project-indexes.json",
                         public_pointer=self.root / "pointer.json",
                         source_snapshot_root=self.root / "snapshots",
                         operator_approved=True, laboratory_mode=True)

    def call(self):
        return laboratory_provenance_gated_swap(
            "demo", "old", self.candidate, {"project_id": "demo"},
            self.root / "baseline.json", Mock(), **self.args)

    @patch("rag.runtime.knowledge_deletion_provenance_swap_lab.laboratory_verified_swap")
    @patch("rag.runtime.knowledge_deletion_provenance_swap_lab.audit_private_removal_candidate")
    def test_changed_snapshot_proof_is_rejected_during_locked_check(self, audit, swap):
        changed = {**self.proof, "snapshot_inventory_sha256": "d" * 64}
        audit.side_effect = [self.proof, changed]
        def simulate_locked_check(*args, **kwargs):
            kwargs["_locked_provenance_check"]()
            raise AssertionError("must never proceed to catalog writer")
        swap.side_effect = simulate_locked_check
        with self.assertRaises(DeletionEvidenceGateError):
            self.call()
        self.assertEqual(audit.call_count, 2)

    @patch("rag.runtime.knowledge_deletion_provenance_swap_lab.laboratory_verified_swap")
    @patch("rag.runtime.knowledge_deletion_provenance_swap_lab.audit_private_removal_candidate")
    def test_unchanged_provenance_allows_lab_callback_only(self, audit, swap):
        audit.return_value = self.proof
        def simulate_locked_check(*args, **kwargs):
            kwargs["_locked_provenance_check"]()
            return {"state": "LAB_SWAP_ACTIVE", "operational_use_allowed": False}
        swap.side_effect = simulate_locked_check
        outcome = self.call()
        self.assertEqual(audit.call_count, 2)
        self.assertFalse(outcome["operational_use_allowed"])
        self.assertEqual(outcome["snapshot_inventory_sha256"], "b" * 64)