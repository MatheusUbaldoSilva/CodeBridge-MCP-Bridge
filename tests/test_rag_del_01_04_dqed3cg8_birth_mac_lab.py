"""DQ-E-D-3C-G-8: birth is included in a domain-separated MAC transcript."""
from unittest import TestCase
from rag.runtime.knowledge_deletion_channel_mac_lab import (
    issue_lab_secret,sign_lab_birth_response,verify_lab_birth_response,
)
class BirthBoundMacTests(TestCase):
    def setUp(self):
        self.secret=issue_lab_secret()
        self.fields=dict(creation_filetime=134000000000000000,
            session_id="a"*64,challenge="b"*64,request_sha256="c"*64,
            project_id="scratch",generation="lab",child_pid=12345)
        self.mac=sign_lab_birth_response(self.secret,**self.fields)
    def test_birth_bound_roundtrip(self):
        self.assertTrue(verify_lab_birth_response(self.secret,self.mac,**self.fields))
    def test_changed_birth_is_rejected(self):
        self.assertFalse(verify_lab_birth_response(self.secret,self.mac,
            **(self.fields|{"creation_filetime":self.fields["creation_filetime"]+1})))
    def test_changed_pid_is_rejected(self):
        self.assertFalse(verify_lab_birth_response(self.secret,self.mac,
            **(self.fields|{"child_pid":23456})))
    def test_changed_challenge_is_rejected(self):
        self.assertFalse(verify_lab_birth_response(self.secret,self.mac,
            **(self.fields|{"challenge":"d"*64})))
    def test_session_reuse_is_rejected(self):
        self.assertFalse(verify_lab_birth_response(self.secret,self.mac,
            **(self.fields|{"session_id":"d"*64})))
    def test_bad_birth_type_is_rejected(self):
        for value in (True,0,-1,"134000000000000000"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    sign_lab_birth_response(self.secret,
                        **(self.fields|{"creation_filetime":value}))
    def test_old_mac_not_accepted(self):
        from rag.runtime.knowledge_deletion_channel_mac_lab import sign_lab_response
        old=sign_lab_response(self.secret,**{
            k:v for k,v in self.fields.items() if k!="creation_filetime"})
        self.assertFalse(verify_lab_birth_response(self.secret,old,**self.fields))
