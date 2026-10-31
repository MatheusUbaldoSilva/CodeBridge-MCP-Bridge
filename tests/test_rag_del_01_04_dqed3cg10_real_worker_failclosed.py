"""DQ-E-D-3C-G-10: real worker MAC scratch fail-closed negative CLI."""
from unittest import TestCase
import json,subprocess,sys
from rag.runtime.knowledge_deletion_channel_mac_lab import issue_lab_secret

WORKER=[sys._base_executable,"-B","-m","rag.runtime.isolated_project_worker"]

class WorkerMacScratchDenyTests(TestCase):
    def call(self,argv,payload=b""):
        return subprocess.run([*WORKER,*argv],input=payload,
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=7,check=False)
    def test_missing_payload_rejected(self):
        result=self.call(["--pinned-mac-scratch"])
        self.assertNotEqual(result.returncode,0)
        self.assertNotIn(b"mac",result.stdout)
    def test_bad_json_rejected(self):
        result=self.call(["--pinned-mac-scratch"],b"{not json}\n")
        self.assertNotEqual(result.returncode,0)
    def test_other_arguments_rejected(self):
        result=self.call(["--pinned-mac-scratch","--extra"],b"{}\n")
        self.assertNotEqual(result.returncode,0)
    def test_private_project_not_resolved_with_bad_payload(self):
        secret=issue_lab_secret()
        payload=json.dumps(dict(secret=secret.hex(),session_id="a"*64,
            challenge="b"*64,request_sha256="c"*64,
            project_id="newworldpvp",generation="lab",
            extra_field="not-allowed")).encode()+b"\n"
        result=self.call(["--pinned-mac-scratch"],payload)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(result.stdout,b"")
        self.assertNotIn(secret.hex().encode(),result.stderr)
    def test_unknown_flag_fails_closed(self):
        result=self.call(["--delete-project"],b"{}\n")
        self.assertNotEqual(result.returncode,0)
    def test_unexpected_extra_frame_rejected_by_payload_schema(self):
        payload=json.dumps({"secret":"x"}).encode()+b"\n"
        result=self.call(["--pinned-mac-scratch"],payload)
        self.assertNotEqual(result.returncode,0)
    def test_unbounded_line_rejected(self):
        result=self.call(["--pinned-mac-scratch"],b"x"*9000+b"\n")
        self.assertNotEqual(result.returncode,0)
