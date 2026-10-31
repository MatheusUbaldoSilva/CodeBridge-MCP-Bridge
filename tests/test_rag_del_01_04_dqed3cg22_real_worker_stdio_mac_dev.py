"""G-22: real Win32 worker scratch pipe descriptor HMAC binding."""
from unittest import TestCase
from unittest.mock import patch
import rag.runtime.knowledge_deletion_mac_pipe_parent_lab as parent

class RealWorkerStdioMacBindingTests(TestCase):
    def test_real_worker_v2_hmac_and_three_pipe_receipts(self):
        proof=parent.scratch_mac_pipe_roundtrip(entrypoint="real-worker")
        self.assertTrue(proof["mac_verified"])
        self.assertTrue(proof["child_parent_stdio_descriptors_matched"])
        self.assertFalse(proof["secure_handle_acl_attested"])
        self.assertFalse(proof["operational_use_allowed"])
    def test_synthetic_worker_same_protocol(self):
        proof=parent.scratch_mac_pipe_roundtrip(entrypoint="synthetic")
        self.assertTrue(proof["child_parent_stdio_descriptors_matched"])
        self.assertFalse(proof["activation_authorized"])
    def test_parent_side_descriptor_forgery_is_rejected(self):
        actual=parent.inspect_pipe_fd_acl_dev
        called=[]
        spawned=[]
        original_spawn=parent.subprocess.Popen
        def record_spawn(*a,**kw):
            p=original_spawn(*a,**kw)
            spawned.append(p)
            return p
        def fake_one(fd):
            data=dict(actual(fd))
            called.append(fd)
            if len(called)==1:
                data["descriptor_digest"]="0"*64
            return data
        with patch.object(parent,"inspect_pipe_fd_acl_dev",side_effect=fake_one),             patch.object(parent.subprocess,"Popen",side_effect=record_spawn):
            with self.assertRaisesRegex(RuntimeError,"scratch child stdio descriptor mismatch"):
                parent.scratch_mac_pipe_roundtrip(entrypoint="real-worker")
        self.assertEqual(len(spawned),1)
        self.assertIsNotNone(spawned[0].poll())
        self.assertTrue(all(s.closed for s in
            (spawned[0].stdin,spawned[0].stdout,spawned[0].stderr)))
    def test_bad_project_still_blocked(self):
        with self.assertRaises(ValueError):
            parent.scratch_mac_pipe_roundtrip(project_id="newworldpvp",
                                              entrypoint="real-worker")
    def test_multiple_roundtrips_never_authorize(self):
        for _ in range(3):
            result=parent.scratch_mac_pipe_roundtrip(entrypoint="real-worker")
            self.assertTrue(result["mac_verified"])
            self.assertFalse(result["activation_authorized"])
