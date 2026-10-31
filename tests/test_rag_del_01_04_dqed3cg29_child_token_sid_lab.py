"""G-29 read-only scratch process token principal relationship tests."""
import subprocess
import sys
from unittest import TestCase
from unittest.mock import patch
from rag.runtime import knowledge_deletion_child_token_observer_dev as observer

class ChildTokenLineageTests(TestCase):
    def test_current_process_same_sid_not_isolated(self):
        proof=observer.inspect_child_token_identity_scratch(
            int(observer._GetCurrentProcess()))
        self.assertTrue(proof["child_token_inspected"])
        self.assertTrue(proof["parent_child_account_sid_equal"])
        self.assertFalse(proof["effective_token_isolation_attested"])
        self.assertFalse(proof["activation_authorized"])
    def test_child_process_created_under_same_account(self):
        p=subprocess.Popen([sys._base_executable,"-B","-c",
            "import time;time.sleep(4)"],stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
            close_fds=True)
        try:
            proof=observer.inspect_child_token_identity_scratch(int(p._handle))
            self.assertTrue(proof["child_token_inspected"])
            self.assertTrue(proof["parent_child_account_sid_equal"])
            self.assertFalse(proof["child_appcontainer"])
            self.assertFalse(proof["effective_acl_attested"])
        finally:
            if p.poll() is None:p.kill();p.wait()
    def test_invalid_handle_input_fails_closed(self):
        for bad in (0,-1,False,None,"45"):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                observer.inspect_child_token_identity_scratch(bad)
    def test_non_process_handle_not_attested(self):
        p=observer.inspect_child_token_identity_scratch(0xFFFFFFFC)
        self.assertFalse(p["child_token_inspected"])
        self.assertFalse(p["operational_use_allowed"])
    def test_missing_child_token_does_not_grant(self):
        original=observer._OpenProcessToken
        calls=[0]
        def mock_one(*args,**kwargs):
            calls[0]+=1
            if calls[0]==2:return False
            return original(*args,**kwargs)
        with patch.object(observer,"_OpenProcessToken",side_effect=mock_one):
            proof=observer.inspect_child_token_identity_scratch(
                int(observer._GetCurrentProcess()))
        self.assertFalse(proof["child_token_inspected"])
        self.assertFalse(proof["activation_authorized"])
