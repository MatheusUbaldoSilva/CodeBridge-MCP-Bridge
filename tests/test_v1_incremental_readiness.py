import unittest
from author_mcp.v1_incremental_readiness import summarize


class IncrementalReadinessReportTests(unittest.TestCase):
    def _probe(self):
        return {"operation_ok": True, "state": "PUBLIC_READER_PROBE_PASS",
                "details": {"mcp_pid": 1, "generation": "legacy",
                            "loaded_reader_functions": {"search": True, "context": True, "status": True},
                            "writer_blocked_during_read": True,
                            "semantic_worker_serialization_loaded": True}}

    def _integrity(self):
        return {"operation_ok": True, "details": {"state": "OBSERVED_CONSISTENT",
                "audited_generation": "legacy", "documents": 210, "chunks": 8761}}

    def _preview(self):
        return {"operation_ok": True, "executed": False, "action": "PLAN",
                "plan": {"candidate_count": 1, "review_status": "FINGERPRINTED_NOT_APPROVED",
                         "incremental_preview": {"new_count": 1,
                         "publication_gate": {"reasons": ["OPERATOR_MAINTENANCE_AUTHORIZATION_REQUIRED"]}}}}

    def test_healthy_readers_are_never_publication_authorization(self):
        report=summarize(self._probe(),self._integrity(),self._preview())
        self.assertEqual(report["state"], "GO_LIVE_BLOCKED")
        self.assertFalse(report["activation_authorized"])
        self.assertFalse(report["safe_to_publish"])
        self.assertTrue(report["public_reader"]["public_runtime_ready_for_hybrid_acceptance"])
        self.assertIn("OPERATOR_MAINTENANCE_AUTHORIZATION_REQUIRED",report["blockers"])

    def test_failed_probes_add_explicit_blockers(self):
        probe=self._probe()
        probe["state"]="PUBLIC_READER_PROBE_BLOCKED"
        preview=self._preview()
        preview["executed"]=True
        report=summarize(probe,{"operation_ok":False},preview)
        self.assertIn("PUBLIC_READER_RUNTIME_NOT_ATTESTED",report["blockers"])
        self.assertIn("PUBLIC_CROSSSTORE_INTEGRITY_NOT_ATTESTED",report["blockers"])
        self.assertIn("DRY_RUN_NOT_CONFIRMED",report["blockers"])
        self.assertFalse(report["safe_to_publish"])
