"""G-26: live cross-process Win32 same-end matching on scratch pipes."""
from unittest import TestCase
from unittest.mock import patch
import rag.runtime.knowledge_deletion_remote_handle_parent_lab as parent

class RemoteRealProcessSameEndTests(TestCase):
    def test_three_child_handles_same_object_as_parent_child_ends(self):
        proof=parent.scratch_remote_same_end_roundtrip()
        self.assertEqual(proof["state"],"SCRATCH_CROSS_PROCESS_SAME_END_HANDLES_MATCHED")
        self.assertEqual(proof["same_end_handles_match"],
                         {"stdin":True,"stdout":True,"stderr":True})
        self.assertTrue(proof["child_pid_and_win32_birth_matched"])
        self.assertFalse(proof["token_effective_acl_attested"])
        self.assertFalse(proof["operational_use_allowed"])
    def test_repeated_real_subprocess_roundtrips(self):
        for _ in range(5):
            proof=parent.scratch_remote_same_end_roundtrip()
            self.assertEqual(len(proof["same_end_handles_match"]),3)
    def test_false_compare_blocks_and_reaps(self):
        original=parent.subprocess.Popen
        children=[]
        def track(*args,**kwargs):
            p=original(*args,**kwargs)
            children.append(p)
            return p
        with patch.object(parent,"compare_remote_same_end_pipe_handle_scratch",
                return_value={"same_kernel_object":False}),             patch.object(parent.subprocess,"Popen",side_effect=track):
            with self.assertRaisesRegex(RuntimeError,"same-end handle mismatch"):
                parent.scratch_remote_same_end_roundtrip()
        self.assertEqual(len(children),1)
        self.assertIsNotNone(children[0].poll())
    def test_invalid_input_fails_before_spawn(self):
        for invalid in (0,.05,False,"3",11):
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):
                parent.scratch_remote_same_end_roundtrip(timeout_seconds=invalid)
    def test_bad_response_shape_is_denied(self):
        with patch.object(parent,"_read_scratch_line",
                          return_value=b'{"pid":1}\n'):
            with self.assertRaisesRegex(RuntimeError,"receipt malformed"):
                parent.scratch_remote_same_end_roundtrip()
    def test_wrong_challenge_denied(self):
        with patch.object(parent,"_read_scratch_line",
                          return_value=b'{"pid":1,"birth":1,"challenge":"bad","std_handles":{}}\n'):
            with self.assertRaisesRegex(RuntimeError,"challenge mismatch"):
                parent.scratch_remote_same_end_roundtrip()
    def test_timeout_is_bounded(self):
        with patch.object(parent,"_read_scratch_line",
                          side_effect=RuntimeError("scratch child receipt timeout")):
            with self.assertRaisesRegex(RuntimeError,"receipt timeout"):
                parent.scratch_remote_same_end_roundtrip(timeout_seconds=.5)
