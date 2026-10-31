"""G-20 readonly Win32 stdio descriptor receipt child tests."""
import json
import subprocess
import sys
from unittest import TestCase
from rag.runtime.knowledge_deletion_pipe_acl_inspection_dev import inspect_pipe_fd_acl_dev

CMD=[sys._base_executable,"-B","-m",
     "rag.runtime.knowledge_deletion_std_handle_receipt_child_lab"]

class NativeStdioReceiptsTests(TestCase):
    def launch(self,stdout=subprocess.PIPE):
        process=subprocess.Popen(CMD,stdin=subprocess.PIPE,stdout=stdout,
                                 stderr=subprocess.PIPE,close_fds=True)
        try:
            parents={
                "stdin":inspect_pipe_fd_acl_dev(process.stdin.fileno()),
                "stderr":inspect_pipe_fd_acl_dev(process.stderr.fileno())}
            if process.stdout is not None:
                parents["stdout"]=inspect_pipe_fd_acl_dev(process.stdout.fileno())
            out,err=process.communicate(timeout=8)
            return process.returncode,out,err,parents
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
    def test_real_child_receipts_match_parent_pipe_descriptors(self):
        code,out,err,parents=self.launch()
        self.assertEqual((code,err),(0,b""))
        data=json.loads(out)
        for name in ("stdin","stdout","stderr"):
            self.assertEqual(data["receipts"][name]["descriptor_sha256"],
                             parents[name]["descriptor_digest"])
            self.assertEqual(data["receipts"][name]["type"],"PIPE")
        self.assertFalse(data["kernel_object_identity_attested"])
        self.assertFalse(data["activation_authorized"])
    def test_child_inheritance_observed_not_authorized(self):
        code,out,_,_=self.launch()
        self.assertEqual(code,0)
        data=json.loads(out)
        self.assertTrue(all(item["inheritable"] for item in data["receipts"].values()))
        self.assertFalse(data["acl_effective_access_attested"])
    def test_child_rejects_stdout_to_null(self):
        code,out,err,_=self.launch(stdout=subprocess.DEVNULL)
        self.assertNotEqual(code,0)
        self.assertIsNone(out)
        self.assertIn(b"not pipe",err)
    def test_no_raw_descriptor_data(self):
        _,out,_,_=self.launch()
        self.assertNotIn(b"S-1-",out)
        self.assertNotIn(b"SDDL",out)
    def test_fresh_child_not_authorized(self):
        for _ in range(2):
            code,out,err,_=self.launch()
            self.assertEqual((code,err),(0,b""))
            self.assertFalse(json.loads(out)["operational_use_allowed"])
