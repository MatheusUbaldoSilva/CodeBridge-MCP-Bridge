"""DQ-E-D-3C-G-4: synthetic MAC protocol tests."""
from unittest import TestCase
from rag.runtime.knowledge_deletion_channel_mac_lab import (
    issue_lab_secret,sign_lab_response,verify_lab_response,
)

def fields():
    return dict(session_id="a"*64,challenge="b"*64,request_sha256="c"*64,
        project_id="newworldpvp",generation="lab-generation",child_pid=4321)

class ChannelMacLabTests(TestCase):
    def setUp(self):
        self.secret=issue_lab_secret()
        self.claim=fields()
        self.mac=sign_lab_response(self.secret,**self.claim)
    def test_256_bit_secret(self):
        self.assertEqual(len(self.secret),32)
        self.assertNotEqual(self.secret,issue_lab_secret())
    def test_exact_roundtrip(self):
        self.assertTrue(verify_lab_response(self.secret,self.mac,**self.claim))
    def test_wrong_secret_rejected(self):
        self.assertFalse(verify_lab_response(issue_lab_secret(),self.mac,**self.claim))
    def test_changed_session_rejected(self):
        self.assertFalse(verify_lab_response(self.secret,self.mac,**(self.claim|{"session_id":"d"*64})))
    def test_replayed_challenge_rejected(self):
        self.assertFalse(verify_lab_response(self.secret,self.mac,**(self.claim|{"challenge":"d"*64})))
    def test_changed_request_rejected(self):
        self.assertFalse(verify_lab_response(self.secret,self.mac,**(self.claim|{"request_sha256":"d"*64})))
    def test_wrong_project_generation_rejected(self):
        for change in ({"project_id":"codebridge"},{"generation":"other"}):
            with self.subTest(change=change):
                self.assertFalse(verify_lab_response(self.secret,self.mac,**(self.claim|change)))
    def test_wrong_child_pid_rejected(self):
        self.assertFalse(verify_lab_response(self.secret,self.mac,**(self.claim|{"child_pid":4322})))
    def test_missing_mac_rejected(self):
        for value in (None,"", "x"*64,"a"*63):
            self.assertFalse(verify_lab_response(self.secret,value,**self.claim))
    def test_bad_secret_rejected(self):
        for value in (None,"abc",b"short"):
            with self.assertRaises(ValueError):
                sign_lab_response(value,**self.claim)
    def test_noncanonical_fields_rejected(self):
        for change in ({"child_pid":True},{"session_id":"BAD"},{"challenge":"b"*63}):
            with self.assertRaises(ValueError):
                sign_lab_response(self.secret,**(self.claim|change))
