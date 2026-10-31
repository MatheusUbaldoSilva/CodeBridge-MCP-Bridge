"""G-16 child-side Win32 std handle type verification."""
import subprocess
import sys
from unittest import TestCase
from unittest.mock import patch
import rag.runtime.knowledge_deletion_child_stdio_lab as guard
from rag.runtime.knowledge_deletion_mac_pipe_parent_lab import scratch_mac_pipe_roundtrip

class ScratchChildStdioWin32Tests(TestCase):
    def test_all_native_std_handles_pipe(self):
        with patch.object(guard,"_GET_STD",side_effect=[101,102,103]),             patch.object(guard,"_GET_TYPE",return_value=3):
            proof=guard.assert_scratch_stdio_pipes_win32()
        self.assertTrue(proof["three_pipe_types_observed"])
        self.assertFalse(proof["child_acl_trusted"])
        self.assertFalse(proof["activation_authorized"])
    def test_one_nonpipe_type_rejected(self):
        with patch.object(guard,"_GET_STD",side_effect=[101,102,103]),             patch.object(guard,"_GET_TYPE",side_effect=[3,1,3]):
            with self.assertRaises(PermissionError):
                guard.assert_scratch_stdio_pipes_win32()
    def test_missing_std_handle_rejected(self):
        with patch.object(guard,"_GET_STD",return_value=0):
            with self.assertRaises(PermissionError):
                guard.assert_scratch_stdio_pipes_win32()
    def test_real_worker_pipe_roundtrip_passes(self):
        r=scratch_mac_pipe_roundtrip(entrypoint="real-worker")
        self.assertTrue(r["mac_verified"])
        self.assertFalse(r["operational_use_allowed"])
    def test_stdio_redirected_to_devnull_rejected(self):
        result=subprocess.run(
            [sys._base_executable,"-B","-m",
             "rag.runtime.isolated_project_worker","--pinned-mac-scratch"],
            input=b"{}\n",stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,
            timeout=8,check=False,
        )
        self.assertNotEqual(result.returncode,0)
        self.assertIn(b"not a pipe",result.stderr)
