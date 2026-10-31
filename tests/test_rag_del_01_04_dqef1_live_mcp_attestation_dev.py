"""RAG-DEL DQ-E-F-1 fail-closed live MCP evidence tests."""
from unittest import TestCase

from rag.runtime.knowledge_deletion_live_mcp_attestation_dev import (
    review_live_generation_probe_dev,
)


TOOL = ["codebridge_rag_status", "codebridge_rag_generation_probe"]


def evidence() -> dict:
    return {
        "operation_ok": True,
        "state": "PUBLIC_READER_PROBE_PASS",
        "safe_to_activate": False,
        "details": {
            "mcp_pid": 1184,
            "generation": "v1_delta_example",
            "loaded_reader_functions": {
                "search": True, "context": True, "status": True,
            },
            "writer_blocked_during_read": True,
            "semantic_worker_serialization_loaded": True,
            "safe_to_activate": False,
        },
    }


class LiveMcpAttestationTests(TestCase):
    def review(self, probe=None, tools=None, readonly=True, pid=1184):
        return review_live_generation_probe_dev(
            TOOL if tools is None else tools,
            evidence() if probe is None else probe,
            read_only_hint=readonly, expected_pid=pid,
        )

    def test_valid_evidence_still_never_authorizes_deletion(self):
        result = self.review()
        self.assertEqual(result["state"], "LIVE_MCP_READERS_OBSERVED_READ_ONLY")
        self.assertTrue(result["live_mcp_probe_attested"])
        self.assertFalse(result["child_semantic_execution_attested"])
        self.assertFalse(result["ready_for_operational_pilot"])
        self.assertFalse(result["activation_authorized"])
        self.assertFalse(result["operational_use_allowed"])

    def test_unlisted_tool_rejected(self):
        self.assertIn("tool_listed", self.review(tools=["codebridge_rag_status"])["blockers"])

    def test_missing_annotation_fails_closed(self):
        self.assertIn("tool_declared_read_only", self.review(readonly=False)["blockers"])

    def test_pid_mismatch_blocks_claim(self):
        self.assertIn("pid_matches_observed_listener", self.review(pid=100)["blockers"])

    def test_missing_reader_blocks_claim(self):
        item = evidence()
        item["details"]["loaded_reader_functions"].pop("context")
        self.assertIn("reader_functions_loaded", self.review(item)["blockers"])

    def test_failure_response_rejected(self):
        item = evidence()
        item["operation_ok"] = False
        self.assertIn("probe_success", self.review(item)["blockers"])

    def test_safe_to_activate_not_accepted(self):
        item = evidence()
        item["safe_to_activate"] = True
        self.assertIn("probe_does_not_authorize", self.review(item)["blockers"])

    def test_bad_pid_is_rejected(self):
        for bad in (True, 0, -1, "1184"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    self.review(pid=bad)

    def test_malformed_evidence_is_not_valid(self):
        for bad in (None, [], "yes"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    review_live_generation_probe_dev(TOOL, bad, read_only_hint=True, expected_pid=1184)

    def test_lack_of_generation_blocks(self):
        item = evidence()
        item["details"]["generation"] = ""
        self.assertIn("runtime_generation_present", self.review(item)["blockers"])