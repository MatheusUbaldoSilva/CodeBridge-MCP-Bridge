"""F-10: chronology guards for Windows GUI topology."""
from pathlib import Path
from unittest import TestCase
from rag.runtime.knowledge_deletion_gui_creation_order_dev import review_gui_creation_order_dev as review

ROOT=Path("C:/Users/Matheus/CodeBridge-MCP-Bridge")

def sample():
    launcher=ROOT.parent/"CodeBridge-Launcher"/"launcher.py"
    gui=ROOT/"app_rewrite"/"main.py"
    mcp=ROOT/"author_mcp"/"mcp_server.py"
    return [
        dict(ProcessId=100,ParentProcessId=1,CreationEpochMs=1000,
             CommandLine='"C:/python/pythonw.exe" "'+str(launcher)+'"'),
        dict(ProcessId=200,ParentProcessId=100,CreationEpochMs=1100,
             CommandLine='"C:/python/python.exe" "'+str(gui)+'" --no-elevate'),
        dict(ProcessId=300,ParentProcessId=200,CreationEpochMs=1200,
             CommandLine='"C:/python/python.exe" "'+str(mcp)+'" --host 127.0.0.1 --port 8765'),
    ]

class GUIBirthOrderTests(TestCase):
    def test_order_observed_not_installed_attestation(self):
        r=review(sample(),ROOT)
        self.assertTrue(r["process_creation_order_observed"])
        self.assertFalse(r["installed_gui_runtime_attested"])
        self.assertFalse(r["activation_authorized"])
    def test_gui_predates_launcher_is_rejected(self):
        x=sample()
        x[1]["CreationEpochMs"]=900
        self.assertFalse(review(x,ROOT)["process_creation_order_observed"])
    def test_mcp_predates_gui_is_rejected(self):
        x=sample()
        x[2]["CreationEpochMs"]=1090
        self.assertFalse(review(x,ROOT)["process_creation_order_observed"])
    def test_absent_birth_fails_closed(self):
        x=sample()
        del x[2]["CreationEpochMs"]
        self.assertFalse(review(x,ROOT)["process_creation_order_observed"])
    def test_boolean_and_string_birth_fail_closed(self):
        for value in (True,"1200",0,None,-1):
            x=sample()
            x[2]["CreationEpochMs"]=value
            with self.subTest(value=value):
                self.assertFalse(review(x,ROOT)["process_creation_order_observed"])
    def test_wrong_pid_parent_rejected(self):
        x=sample()
        x[2]["ParentProcessId"]=999
        self.assertFalse(review(x,ROOT)["process_creation_order_observed"])
    def test_cyclic_lineage_not_accepted(self):
        x=sample()
        x[0]["ParentProcessId"]=300
        x[2]["CreationEpochMs"]=100
        self.assertFalse(review(x,ROOT)["process_creation_order_observed"])

    def test_f11_shadowed_port_breaks_birth_observation(self):
        x=sample()
        x[2]["CommandLine"]+=" --port 9999"
        result=review(x,ROOT)
        self.assertFalse(result["process_creation_order_observed"])
        self.assertFalse(result["activation_authorized"])

    def test_f11_nonloopback_host_breaks_birth_observation(self):
        x=sample()
        x[2]["CommandLine"]=x[2]["CommandLine"].replace(
            "--host 127.0.0.1","--host 0.0.0.0")
        self.assertFalse(review(x,ROOT)["process_creation_order_observed"])

    def test_f11_reordered_exact_mcp_flags_still_observed(self):
        x=sample()
        x[2]["CommandLine"]=x[2]["CommandLine"].replace(
            "--host 127.0.0.1 --port 8765",
            "--port 8765 --host 127.0.0.1")
        r=review(x,ROOT)
        self.assertTrue(r["process_creation_order_observed"])
        self.assertFalse(r["installed_gui_runtime_attested"])
