"""G-28 real-process remote handle HMAC adversarial tests."""
from unittest import TestCase
from unittest.mock import patch
import json
import rag.runtime.knowledge_deletion_remote_handle_parent_lab as parent

class NativeSameEndMacIntegrationTests(TestCase):
    def test_live_child_mac_and_same_end_identity(self):
        proof=parent.scratch_remote_same_end_roundtrip()
        self.assertTrue(proof["native_handle_hmac_verified"])
        self.assertTrue(proof["child_pid_and_win32_birth_matched"])
        self.assertEqual(set(proof["same_end_handles_match"]),{"stdin","stdout","stderr"})
        self.assertFalse(proof["activation_authorized"])
    def test_fake_mac_rejected_before_object_comparisons(self):
        actual=parent._read_scratch_line
        def tamper(*args,**kwargs):
            obj=json.loads(actual(*args,**kwargs))
            obj["mac"]="0"*64
            return json.dumps(obj).encode()+b"\n"
        with patch.object(parent,"_read_scratch_line",side_effect=tamper),             patch.object(parent,"compare_remote_same_end_pipe_handle_scratch",
                          side_effect=AssertionError("do not compare unauthenticated handles")):
            with self.assertRaisesRegex(RuntimeError,"native handle MAC mismatch"):
                parent.scratch_remote_same_end_roundtrip()
    def test_changed_native_handle_rejected(self):
        actual=parent._read_scratch_line
        def tamper(*args,**kwargs):
            obj=json.loads(actual(*args,**kwargs))
            obj["std_handles"]["stdout"]+=4
            return json.dumps(obj).encode()+b"\n"
        with patch.object(parent,"_read_scratch_line",side_effect=tamper):
            with self.assertRaisesRegex(RuntimeError,"native handle MAC mismatch"):
                parent.scratch_remote_same_end_roundtrip()
    def test_repeated_run_independent_sessions(self):
        for _ in range(3):
            proof=parent.scratch_remote_same_end_roundtrip()
            self.assertTrue(proof["native_handle_hmac_verified"])
            self.assertFalse(proof["child_binary_trusted_for_production"])
