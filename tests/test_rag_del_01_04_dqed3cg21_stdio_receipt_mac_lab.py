"""G-21 scratch pipe descriptor receipt MAC negative tests."""
from unittest import TestCase
from rag.runtime.knowledge_deletion_channel_mac_lab import issue_lab_secret
from rag.runtime.knowledge_deletion_pipe_receipt_mac_lab import sign_lab_stdio_receipts,verify_lab_stdio_receipts

class ScratchStdioMacContractTests(TestCase):
    def setUp(self):
        self.secret=issue_lab_secret()
        self.args=dict(session_id="a"*64,challenge="b"*64,
           request_sha256="c"*64,project_id="scratch",generation="lab",
           child_pid=18604,creation_filetime=134000000000000000,
           stdio_receipts=dict(stdin="1"*64,stdout="2"*64,stderr="3"*64))
        self.mac=sign_lab_stdio_receipts(self.secret,**self.args)
    def test_roundtrip(self):
        self.assertTrue(verify_lab_stdio_receipts(self.secret,self.mac,**self.args))
    def test_change_one_pipe_digest_fails(self):
        for fd in ("stdin","stdout","stderr"):
            with self.subTest(fd=fd):
                change=dict(self.args["stdio_receipts"])
                change[fd]="4"*64
                self.assertFalse(verify_lab_stdio_receipts(self.secret,self.mac,
                    **(self.args|{"stdio_receipts":change})))
    def test_change_pid_or_birth_rejected(self):
        for changed in ({"child_pid":18605},{"creation_filetime":134000000000000001}):
            with self.subTest(changed=changed):
                self.assertFalse(verify_lab_stdio_receipts(self.secret,self.mac,
                    **(self.args|changed)))
    def test_replayed_challenge_denied(self):
        self.assertFalse(verify_lab_stdio_receipts(self.secret,self.mac,
            **(self.args|{"challenge":"d"*64})))
    def test_replayed_session_denied(self):
        self.assertFalse(verify_lab_stdio_receipts(self.secret,self.mac,
            **(self.args|{"session_id":"d"*64})))
    def test_wrong_secret_denied(self):
        self.assertFalse(verify_lab_stdio_receipts(issue_lab_secret(),self.mac,**self.args))
    def test_malformed_receipt_keys_denied(self):
        for changed in ({"stdin":"1"*64},{"stdin":"1"*64,"stdout":"2"*64,
                         "stderr":"3"*64,"extra":"0"*64}):
            with self.subTest(changed=changed),self.assertRaises(ValueError):
                sign_lab_stdio_receipts(self.secret,
                    **(self.args|{"stdio_receipts":changed}))
    def test_noncanonical_hex_denied(self):
        changed=dict(self.args["stdio_receipts"])
        changed["stderr"]="A"*64
        with self.assertRaises(ValueError):
            sign_lab_stdio_receipts(self.secret,
                **(self.args|{"stdio_receipts":changed}))
    def test_bad_mac_denied(self):
        self.assertFalse(verify_lab_stdio_receipts(self.secret,"z"*64,**self.args))
    def test_wrong_birth_type_denied(self):
        with self.assertRaises(ValueError):
            sign_lab_stdio_receipts(self.secret,
                **(self.args|{"creation_filetime":True}))
    def test_malformed_secret_denied(self):
        with self.assertRaises(ValueError):
            sign_lab_stdio_receipts(b"short",**self.args)
