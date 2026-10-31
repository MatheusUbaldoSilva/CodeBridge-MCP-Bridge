"""DQ-E-D-3C-G-9: real worker entrypoint must remain scratch only."""
from unittest import TestCase
from rag.runtime.knowledge_deletion_mac_pipe_parent_lab import scratch_mac_pipe_roundtrip

class RealWorkerMacScratchTests(TestCase):
    def test_real_worker_mac_only(self):
        evidence=scratch_mac_pipe_roundtrip(entrypoint="real-worker")
        self.assertTrue(evidence["mac_verified"])
        self.assertTrue(evidence["spawned_pid_matches_response"])
        self.assertTrue(evidence["win32_birth_matches_response"])
        self.assertFalse(evidence["activation_authorized"])
        self.assertFalse(evidence["operational_use_allowed"])
    def test_real_worker_repeat_independent(self):
        a=scratch_mac_pipe_roundtrip(entrypoint="real-worker")
        b=scratch_mac_pipe_roundtrip(entrypoint="real-worker")
        self.assertTrue(a["mac_verified"] and b["mac_verified"])
    def test_unknown_worker_route_denied(self):
        with self.assertRaises(ValueError):
            scratch_mac_pipe_roundtrip(entrypoint="normal")
    def test_real_worker_route_denies_private_namespace(self):
        with self.assertRaises(ValueError):
            scratch_mac_pipe_roundtrip(entrypoint="real-worker",project_id="newworldpvp")
