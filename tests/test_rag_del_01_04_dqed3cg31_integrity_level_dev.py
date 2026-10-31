"""G-31: native Win32 integrity-level observation tests."""
import subprocess
import sys
from unittest import TestCase
from unittest.mock import patch
from rag.runtime import knowledge_deletion_token_integrity_observer_dev as mod

class IntegrityTokenLabTests(TestCase):
    def test_current_process_integrity_never_authorizes(self):
        proof=mod.inspect_scratch_integrity_levels_dev(int(mod._GetCurrentProcess()))
        self.assertEqual(proof["state"],"SCRATCH_TOKEN_INTEGRITY_LABELS_OBSERVED")
        self.assertEqual(proof["parent_integrity"],proof["child_integrity"])
        self.assertFalse(proof["privilege_isolation_attested"])
        self.assertFalse(proof["activation_authorized"])
    def test_real_new_process_same_integrity(self):
        child=subprocess.Popen([sys._base_executable,"-B","-c",
            "import time;time.sleep(3)"],stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,stdin=subprocess.DEVNULL,close_fds=True)
        try:
            r=mod.inspect_scratch_integrity_levels_dev(int(child._handle))
            self.assertEqual(r["state"],"SCRATCH_TOKEN_INTEGRITY_LABELS_OBSERVED")
            self.assertTrue(r["integrity_levels_equal"])
            self.assertFalse(r["operational_use_allowed"])
        finally:
            if child.poll() is None:child.kill();child.wait()
    def test_bad_handle_rejected(self):
        for v in (0,-1,None,True,"7"):
            with self.subTest(v=v),self.assertRaises(ValueError):
                mod.inspect_scratch_integrity_levels_dev(v)
    def test_non_process_handle_not_attested(self):
        r=mod.inspect_scratch_integrity_levels_dev(0xFFFFFFFC)
        self.assertEqual(r["state"],"SCRATCH_TOKEN_INTEGRITY_UNATTESTED")
        self.assertFalse(r["effective_acl_attested"])
    def test_token_query_failure_is_not_authority(self):
        with patch.object(mod,"_OpenProcessToken",return_value=False):
            r=mod.inspect_scratch_integrity_levels_dev(int(mod._GetCurrentProcess()))
        self.assertFalse(r["activation_authorized"])
        self.assertIsNone(r["integrity_levels_equal"])
