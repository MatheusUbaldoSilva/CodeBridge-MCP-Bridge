"""G-27 HMAC same-end Win32 child binding contract."""
from unittest import TestCase
from rag.runtime.knowledge_deletion_remote_handle_mac_lab import (
    sign_remote_handle_lab,verify_remote_handle_lab,
)

class RemoteNativeHandleMacTests(TestCase):
    def setUp(self):
        self.key=b"1"*32
        self.fields=dict(session_id="a"*64,challenge="b"*64,project_id="scratch",
            generation="lab",child_pid=12345,creation_filetime=134000000001234567,
            std_handles={"stdin":100,"stdout":108,"stderr":112})
        self.mac=sign_remote_handle_lab(self.key,**self.fields)
    def test_roundtrip(self):
        self.assertTrue(verify_remote_handle_lab(self.key,self.mac,**self.fields))
    def test_key_separation(self):
        self.assertFalse(verify_remote_handle_lab(b"2"*32,self.mac,**self.fields))
    def test_any_std_handle_changed(self):
        for name in ("stdin","stdout","stderr"):
            changed=dict(self.fields["std_handles"])
            changed[name]+=4
            self.assertFalse(verify_remote_handle_lab(self.key,self.mac,
                **(self.fields|{"std_handles":changed})))
    def test_pid_and_birth_changed(self):
        for change in ({"child_pid":12346},{"creation_filetime":134000000001234568}):
            self.assertFalse(verify_remote_handle_lab(self.key,self.mac,
                **(self.fields|change)))
    def test_session_challenge_replay_denied(self):
        for change in ({"session_id":"c"*64},{"challenge":"c"*64}):
            self.assertFalse(verify_remote_handle_lab(self.key,self.mac,
                **(self.fields|change)))
    def test_private_project_and_nonlab_denied(self):
        for change in ({"project_id":"codebridge"},{"generation":"prod"}):
            with self.assertRaises(ValueError):
                sign_remote_handle_lab(self.key,**(self.fields|change))
    def test_malformed_handles_denied(self):
        for changed in ({"stdin":100},{"stdin":100,"stdout":108,"stderr":False},
                        {"stdin":100,"stdout":108,"stderr":112,"other":120},
                        {"stdin":0,"stdout":108,"stderr":112}):
            with self.assertRaises(ValueError):
                sign_remote_handle_lab(self.key,
                    **(self.fields|{"std_handles":changed}))
    def test_malformed_session(self):
        with self.assertRaises(ValueError):
            sign_remote_handle_lab(self.key,
                **(self.fields|{"session_id":"A"*64}))
    def test_boolean_pid_denied(self):
        with self.assertRaises(ValueError):
            sign_remote_handle_lab(self.key,
                **(self.fields|{"child_pid":True}))
    def test_bad_key_denied(self):
        with self.assertRaises(ValueError):
            sign_remote_handle_lab(b"short",**self.fields)
    def test_bad_signature_denied(self):
        self.assertFalse(verify_remote_handle_lab(self.key,"Z"*64,**self.fields))
