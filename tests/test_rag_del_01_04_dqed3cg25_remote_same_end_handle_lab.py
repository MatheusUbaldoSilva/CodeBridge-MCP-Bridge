"""G-25: single-process proxy checks for native cross-table duplicate wrapper."""
import ctypes
import os
from unittest import TestCase
from ctypes import wintypes
from rag.runtime import knowledge_deletion_remote_handle_compare_lab as mod

class RemoteHandleCompareLabTests(TestCase):
    def setUp(self):
        self.r,self.w=os.pipe()
        self.addCleanup(os.close,self.r)
        self.addCleanup(os.close,self.w)
        self.current=int(mod._GetCurrentProcess())
    def raw(self,fd):
        import msvcrt
        return int(msvcrt.get_osfhandle(fd))
    def test_same_object_in_current_process_proves_native_comparison(self):
        proof=mod.compare_remote_same_end_pipe_handle_scratch(
            child_process_handle=self.current,remote_handle=self.raw(self.r),
            parent_same_end_fd=self.r)
        self.assertTrue(proof["same_kernel_object"])
        self.assertFalse(proof["child_pid_bound"])
        self.assertFalse(proof["activation_authorized"])
    def test_different_pipe_ends_mismatch(self):
        proof=mod.compare_remote_same_end_pipe_handle_scratch(
            child_process_handle=self.current,remote_handle=self.raw(self.w),
            parent_same_end_fd=self.r)
        self.assertEqual(proof["state"],"SCRATCH_REMOTE_SAME_END_MISMATCH")
    def test_same_end_os_dup_matches(self):
        dup=os.dup(self.r)
        self.addCleanup(os.close,dup)
        proof=mod.compare_remote_same_end_pipe_handle_scratch(
            child_process_handle=self.current,remote_handle=self.raw(dup),
            parent_same_end_fd=self.r)
        self.assertTrue(proof["same_kernel_object"])
    def test_invalid_remote_handle_fails_closed(self):
        proof=mod.compare_remote_same_end_pipe_handle_scratch(
            child_process_handle=self.current,remote_handle=0xFFFFFFFC,
            parent_same_end_fd=self.r)
        self.assertFalse(proof["same_kernel_object"])
        self.assertFalse(proof["activation_authorized"])
    def test_types_rejected(self):
        for fields in [
            dict(child_process_handle=False,remote_handle=1,parent_same_end_fd=0),
            dict(child_process_handle=1,remote_handle=0,parent_same_end_fd=0),
            dict(child_process_handle=1,remote_handle=1,parent_same_end_fd=True),
            dict(child_process_handle=1,remote_handle=1,parent_same_end_fd=-1),
        ]:
            with self.subTest(fields=fields),self.assertRaises(ValueError):
                mod.compare_remote_same_end_pipe_handle_scratch(**fields)
    def test_closed_fd_fails_closed(self):
        fd=os.dup(self.r)
        os.close(fd)
        proof=mod.compare_remote_same_end_pipe_handle_scratch(
            child_process_handle=self.current,remote_handle=self.raw(self.r),
            parent_same_end_fd=fd)
        self.assertFalse(proof["imported_pipe_handle"])
    def test_receipt_never_claims_operational_privileges(self):
        proof=mod.compare_remote_same_end_pipe_handle_scratch(
            child_process_handle=self.current,remote_handle=self.raw(self.r),
            parent_same_end_fd=self.r)
        self.assertFalse(proof["installed_gui_attested"])
        self.assertFalse(proof["operational_use_allowed"])
        self.assertFalse(proof["child_birth_bound"])
