"""G-15: scratch parent observes all three pipe ends before sending secret."""
from unittest import TestCase
from unittest.mock import patch
import rag.runtime.knowledge_deletion_mac_pipe_parent_lab as parent

class ScratchParentPipeInspectionTests(TestCase):
    def test_synthetic_worker_descriptor_observed(self):
        r=parent.scratch_mac_pipe_roundtrip(entrypoint="synthetic")
        self.assertTrue(r["parent_pipe_descriptors_observed"])
        self.assertTrue(r["parent_pipe_ends_not_inheritable"])
        self.assertFalse(r["secure_handle_acl_attested"])
        self.assertFalse(r["activation_authorized"])
    def test_real_worker_descriptor_observed(self):
        r=parent.scratch_mac_pipe_roundtrip(entrypoint="real-worker")
        self.assertTrue(r["mac_verified"])
        self.assertTrue(r["parent_pipe_descriptors_observed"])
        self.assertFalse(r["operational_use_allowed"])
    def assert_reject_unverified(self,override):
        processes=[]
        original=parent.subprocess.Popen
        def capturing_spawn(*args,**kwargs):
            p=original(*args,**kwargs)
            processes.append(p)
            return p
        with patch.object(parent,"inspect_pipe_fd_acl_dev",return_value=override),             patch.object(parent.subprocess,"Popen",side_effect=capturing_spawn):
            with self.assertRaisesRegex(RuntimeError,"scratch parent pipe security unverified"):
                parent.scratch_mac_pipe_roundtrip()
        self.assertEqual(len(processes),1)
        self.assertIsNotNone(processes[0].poll(),"scratch child was not reaped")
    def test_missing_dacl_fails_closed(self):
        self.assert_reject_unverified(dict(descriptor_observed=True,dacl_present=False,
            owner_present=True,parent_handle_inheritable=False))
    def test_inheritable_parent_pipe_fails_closed(self):
        self.assert_reject_unverified(dict(descriptor_observed=True,dacl_present=True,
            owner_present=True,parent_handle_inheritable=True))
    def test_absent_descriptor_fails_closed(self):
        self.assert_reject_unverified(dict(descriptor_observed=False,dacl_present=False,
            owner_present=False,parent_handle_inheritable=None))
