"""G-23: native CompareObjectHandles distinguishes duplicate vs opposite end."""
import os
from unittest import TestCase
from unittest.mock import patch
import rag.runtime.knowledge_deletion_handle_identity_win32_lab as native

class NativeHandleIdentityTests(TestCase):
    def setUp(self):
        self.r,self.w=os.pipe()
        self.addCleanup(os.close,self.r)
        self.addCleanup(os.close,self.w)
    def test_same_fd_is_same_object(self):
        proof=native.compare_open_fd_objects_win32_dev(self.r,self.r)
        self.assertTrue(proof["same_kernel_object"])
        self.assertFalse(proof["activation_authorized"])
    def test_duplicate_read_end_same_object(self):
        dup=os.dup(self.r)
        self.addCleanup(os.close,dup)
        self.assertTrue(native.compare_open_fd_objects_win32_dev(self.r,dup)["same_kernel_object"])
    def test_duplicate_write_end_same_object(self):
        dup=os.dup(self.w)
        self.addCleanup(os.close,dup)
        self.assertTrue(native.compare_open_fd_objects_win32_dev(self.w,dup)["same_kernel_object"])
    def test_opposite_pipe_ends_not_same_kernel_file_object(self):
        proof=native.compare_open_fd_objects_win32_dev(self.r,self.w)
        self.assertFalse(proof["same_kernel_object"])
        self.assertFalse(proof["cross_process_inheritance_attested"])
    def test_invalid_fd_types_rejected(self):
        for pair in ((None,1),(True,1),(-1,1),(self.r,"4")):
            with self.subTest(pair=pair),self.assertRaises(ValueError):
                native.compare_open_fd_objects_win32_dev(*pair)
    def test_closed_fd_not_attested(self):
        dup=os.dup(self.r)
        os.close(dup)
        proof=native.compare_open_fd_objects_win32_dev(self.r,dup)
        self.assertIsNone(proof["same_kernel_object"])
        self.assertFalse(proof["operational_use_allowed"])
    def test_missing_api_fails_closed(self):
        with patch.object(native,"_COMPARE",None):
            proof=native.compare_open_fd_objects_win32_dev(self.r,self.r)
        self.assertEqual(proof["state"],"SCRATCH_HANDLE_IDENTITY_NOT_ATTESTED")
        self.assertFalse(proof["activation_authorized"])
