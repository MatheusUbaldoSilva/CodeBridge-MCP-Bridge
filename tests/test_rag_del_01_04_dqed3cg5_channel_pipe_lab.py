"""DQ-E-D-3C-G-5 private pipe lab tests."""
from unittest import TestCase
from rag.runtime.knowledge_deletion_mac_pipe_parent_lab import scratch_mac_pipe_roundtrip

class PipeProofLabTests(TestCase):
    def test_real_child_pipe_proof(self):
        r=scratch_mac_pipe_roundtrip()
        self.assertTrue(r["mac_verified"])
        self.assertTrue(r["spawned_pid_matches_response"])
        self.assertFalse(r["os_process_identity_attested"])
        self.assertFalse(r["activation_authorized"])
    def test_repeat_has_no_authority(self):
        for _ in range(2):
            self.assertFalse(scratch_mac_pipe_roundtrip()["operational_use_allowed"])
    def test_reject_real_project(self):
        with self.assertRaises(ValueError):
            scratch_mac_pipe_roundtrip(project_id="newworldpvp")
    def test_reject_generation(self):
        with self.assertRaises(ValueError):
            scratch_mac_pipe_roundtrip(generation="v1")
    def test_invalid_timeout(self):
        for value in (True,0,-1,100,"five"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    scratch_mac_pipe_roundtrip(timeout_seconds=value)
