"""G-30: real Win32 HMAC child token query remains non-authorizing."""
from unittest import TestCase
from unittest.mock import patch
import rag.runtime.knowledge_deletion_remote_handle_parent_lab as parent

class RemoteChildTokenGatingTests(TestCase):
    def test_full_native_proof_reports_same_sid_no_isolation(self):
        proof=parent.scratch_remote_same_end_roundtrip()
        self.assertTrue(proof["native_handle_hmac_verified"])
        self.assertTrue(proof["parent_child_account_sid_equal"])
        self.assertFalse(proof["child_appcontainer"])
        self.assertFalse(proof["effective_token_isolation_attested"])
        self.assertFalse(proof["activation_authorized"])
    def test_token_query_unavailable_rejects_and_reaps(self):
        original=parent.subprocess.Popen
        proc_list=[]
        def track(*args,**kw):
            obj=original(*args,**kw)
            proc_list.append(obj)
            return obj
        with patch.object(parent,"inspect_child_token_identity_scratch",
                          return_value={"child_token_inspected":False}),             patch.object(parent.subprocess,"Popen",side_effect=track):
            with self.assertRaisesRegex(RuntimeError,"child token could not be inspected"):
                parent.scratch_remote_same_end_roundtrip()
        self.assertEqual(len(proc_list),1)
        self.assertIsNotNone(proc_list[0].poll())
    def test_token_evidence_does_not_enable_operational_use(self):
        with patch.object(parent,"inspect_child_token_identity_scratch",
                          return_value={
                            "child_token_inspected":True,
                            "parent_child_account_sid_equal":False,
                            "child_appcontainer":True,
                            "effective_token_isolation_attested":True}):
            proof=parent.scratch_remote_same_end_roundtrip()
        self.assertFalse(proof["effective_token_isolation_attested"])
        self.assertFalse(proof["operational_use_allowed"])
        self.assertFalse(proof["activation_authorized"])
