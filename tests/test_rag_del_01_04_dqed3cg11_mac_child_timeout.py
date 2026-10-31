"""G-11: no-response child is killed/reaped when MAC pipe times out."""
from unittest import TestCase
from rag.runtime.knowledge_deletion_mac_pipe_parent_lab import scratch_mac_pipe_roundtrip

class MacChildTimeoutTests(TestCase):
    def test_hang_before_response_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError,"scratch child timeout"):
            scratch_mac_pipe_roundtrip(entrypoint="hang-fixture",timeout_seconds=0.3)
    def test_repeat_timeout_does_not_leave_parent_blocked(self):
        with self.assertRaises(RuntimeError):
            scratch_mac_pipe_roundtrip(entrypoint="hang-fixture",timeout_seconds=0.3)
        self.assertTrue(scratch_mac_pipe_roundtrip(entrypoint="synthetic")["mac_verified"])
    def test_real_worker_survives_fixture_failure(self):
        with self.assertRaises(RuntimeError):
            scratch_mac_pipe_roundtrip(entrypoint="hang-fixture",timeout_seconds=0.3)
        result=scratch_mac_pipe_roundtrip(entrypoint="real-worker")
        self.assertTrue(result["win32_birth_matches_response"])
        self.assertFalse(result["activation_authorized"])
