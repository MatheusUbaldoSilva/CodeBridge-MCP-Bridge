"""G-14: read-only Windows pipe descriptor and inheritability observation."""
import os
from unittest import TestCase
from rag.runtime.knowledge_deletion_pipe_acl_inspection_dev import inspect_pipe_fd_acl_dev as inspect

class PipeAclDescriptorTests(TestCase):
    def setUp(self):
        self.r,self.w=os.pipe()
        self.addCleanup(os.close,self.r)
        self.addCleanup(os.close,self.w)
    def test_descriptor_is_observed(self):
        for fd in (self.r,self.w):
            proof=inspect(fd)
            self.assertEqual(proof["state"],"WIN32_PIPE_ACL_SOURCE_OBSERVED_READ_ONLY")
            self.assertTrue(proof["descriptor_observed"])
            self.assertTrue(proof["dacl_present"])
            self.assertTrue(proof["owner_present"])
    def test_parent_handles_not_inheritable_by_default(self):
        self.assertFalse(inspect(self.r)["parent_handle_inheritable"])
        self.assertFalse(inspect(self.w)["parent_handle_inheritable"])
    def test_manual_inheritability_is_observed_not_authorized(self):
        os.set_inheritable(self.r,True)
        self.assertTrue(inspect(self.r)["parent_handle_inheritable"])
        self.assertFalse(inspect(self.r)["activation_authorized"])
        os.set_inheritable(self.r,False)
        self.assertFalse(inspect(self.r)["parent_handle_inheritable"])
    def test_descriptor_digests_for_two_pipe_ends_equal(self):
        self.assertEqual(inspect(self.r)["descriptor_digest"],inspect(self.w)["descriptor_digest"])
    def test_no_raw_sddl_or_secret(self):
        proof=inspect(self.r)
        self.assertEqual(len(proof["descriptor_digest"]),64)
        self.assertFalse(proof["private_acl_attested"])
        self.assertFalse(proof["child_handle_inheritance_attested"])
        self.assertFalse(proof["operational_use_allowed"])
    def test_bad_fd_rejected(self):
        for value in (None,True,-1,"1"):
            with self.subTest(value=value),self.assertRaises(ValueError):
                inspect(value)
    def test_closed_fd_fails_closed(self):
        fd=os.dup(self.r)
        os.close(fd)
        proof=inspect(fd)
        self.assertFalse(proof["descriptor_observed"])
        self.assertFalse(proof["activation_authorized"])
