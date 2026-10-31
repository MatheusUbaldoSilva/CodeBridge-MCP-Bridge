"""G-18: read-only native Win32 ACE inventory and deny-only policy."""
import ctypes
from ctypes import wintypes
import os
from unittest import TestCase
from unittest.mock import patch
import rag.runtime.knowledge_deletion_pipe_ace_inventory_dev as acl
from rag.runtime.knowledge_deletion_pipe_ace_inventory_dev import inspect_pipe_allow_aces_read_only_dev as inspect

class NativePipeAceInventoryTests(TestCase):
    def setUp(self):
        self.r,self.w=os.pipe()
        self.addCleanup(os.close,self.r)
        self.addCleanup(os.close,self.w)
    def test_inventory_non_authorizing(self):
        proof=inspect(self.r)
        self.assertEqual(proof["state"],"WIN32_PIPE_ACE_INVENTORY_READ_ONLY")
        self.assertTrue(proof["dacl_observed"])
        self.assertGreater(proof["ace_count"],0)
        self.assertEqual(len(proof["aces"]),proof["ace_count"])
        self.assertFalse(proof["private_acl_attested"])
        self.assertFalse(proof["effective_access_attested"])
        self.assertFalse(proof["activation_authorized"])
    def test_each_observed_simple_ace_has_digest(self):
        proof=inspect(self.r)
        self.assertFalse(proof["unsupported_ace_detected"])
        for ace in proof["aces"]:
            self.assertIn(ace["ace_type"],("ALLOW","DENY"))
            self.assertEqual(len(ace["sid_sha256"]),64)
            self.assertEqual(len(ace["access_mask_hex"]),8)
    def test_no_raw_sid_or_token_data_in_result(self):
        text=str(inspect(self.r))
        self.assertNotIn("S-1-5-",text)
        self.assertNotIn("S-1-1-",text)
    def test_ends_are_independently_observed(self):
        left,right=inspect(self.r),inspect(self.w)
        self.assertEqual(left["state"],right["state"])
        self.assertEqual(left["ace_count"],right["ace_count"])
    def test_bad_fd_does_not_call_native(self):
        for bad in (None,False,-1,"3"):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                inspect(bad)
    def test_closed_fd_fails_closed(self):
        other=os.dup(self.r)
        os.close(other)
        result=inspect(other)
        self.assertIn("INVALID_DESCRIPTOR",result["blockers"])
        self.assertFalse(result["activation_authorized"])
    def test_unknown_or_null_security_fails_closed(self):
        with patch.object(acl,"_GetSecurityInfo",return_value=5):
            proof=inspect(self.r)
        self.assertIn("WIN32_SECURITY_QUERY_FAILED",proof["blockers"])
    def test_null_dacl_fails_closed(self):
        with patch.object(acl,"_GetSecurityInfo",return_value=0):
            proof=inspect(self.r)
        self.assertIn("NULL_OR_ABSENT_DACL",proof["blockers"])
    def test_current_handle_does_not_change_inheritability(self):
        before=os.get_inheritable(self.r)
        inspect(self.r)
        self.assertEqual(before,os.get_inheritable(self.r))
    def test_well_known_broad_sid_labels(self):
        win=ctypes.WinDLL("advapi32",use_last_error=True)
        convert=win.ConvertStringSidToSidW
        convert.argtypes=[wintypes.LPCWSTR,ctypes.POINTER(ctypes.c_void_p)]
        convert.restype=wintypes.BOOL
        for name,expected in (("S-1-1-0","EVERYONE"),
                              ("S-1-5-11","AUTHENTICATED_USERS"),
                              ("S-1-5-32-545","BUILTIN_USERS")):
            sid=ctypes.c_void_p()
            self.assertTrue(convert(name,ctypes.byref(sid)))
            try:
                self.assertEqual(acl._sid_label(sid.value)["principal_class"],expected)
            finally:
                acl._LocalFree(sid)
