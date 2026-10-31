"""DQ-E-A: source presence cannot replace installed-reader attestation."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from rag.runtime.knowledge_deletion_dqe_attestation_gate_dev import (
    audit_private_deletion_readiness_dev,
)


class InstalledReaderAttestationGateTests(TestCase):
    def setUp(self):
        self.root=Path(__file__).resolve().parents[1]

    def test_current_code_has_readonly_probe_but_unattested_live_process_blocks(self):
        result=audit_private_deletion_readiness_dev(self.root)
        self.assertTrue(result["observations"][
            "mcp_generation_probe_declared_read_only_in_source"
        ])
        self.assertEqual(result["state"],"DQE_SOURCE_AND_INSTALLATION_GATES_BLOCKED")
        self.assertIn("installed_mcp_generation_probe_exposed",result["missing_gates"])
        self.assertIn("semantic_child_reader_attested",result["missing_gates"])
        self.assertFalse(result["installed_process_verified_by_this_function"])
        self.assertFalse(result["activation_authorized"])
        self.assertFalse(result["ready_for_operational_pilot"])

    def test_even_all_claimed_observations_cannot_authorize_real_deletion(self):
        result=audit_private_deletion_readiness_dev(
            self.root,
            installed_mcp_probe_exposed=True,
            installed_gui_pinned_reader_attested=True,
            semantic_child_reader_attested=True,
            operational_queue_review_clean=True,
        )
        self.assertEqual(result["missing_gates"],())
        self.assertEqual(result["state"],"DQE_EVIDENCE_PRESENT_APPROVAL_STILL_REQUIRED")
        self.assertFalse(result["activation_authorized"])
        self.assertFalse(result["operational_use_allowed"])
        self.assertFalse(result["ready_for_operational_pilot"])
        self.assertFalse(result["live_generation_safe_to_cutover"])

    def test_missing_source_is_never_treated_as_attestation(self):
        with TemporaryDirectory() as td:
            result=audit_private_deletion_readiness_dev(
                Path(td),
                installed_mcp_probe_exposed=True,
                installed_gui_pinned_reader_attested=True,
                semantic_child_reader_attested=True,
                operational_queue_review_clean=True,
            )
        self.assertFalse(result["observations"][
            "mcp_generation_probe_declared_read_only_in_source"
        ])
        self.assertFalse(result["activation_authorized"])

    def test_non_boolean_claims_rejected_instead_of_truthy_coercion(self):
        for value in (1,0,"yes",None,[],{}):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    audit_private_deletion_readiness_dev(
                        self.root,installed_mcp_probe_exposed=value,
                    )