"""DQ-E-F-4 process topology is not module attestation."""
from pathlib import Path
from unittest import TestCase
from rag.runtime.knowledge_deletion_gui_process_observer_dev import review_gui_process_topology_dev as review
ROOT=Path("C:/Users/Matheus/CodeBridge-MCP-Bridge")
def tree():
    return [
        dict(ProcessId=10,ParentProcessId=1,CommandLine=r'C:\Users\Matheus\CodeBridge-Launcher\launcher.py'),
        dict(ProcessId=20,ParentProcessId=10,CommandLine=str(ROOT/"app_rewrite/main.py")+" --no-elevate"),
        dict(ProcessId=30,ParentProcessId=20,CommandLine=str(ROOT/"author_mcp/mcp_server.py")+" --host 127.0.0.1 --port 8765"),
    ]
class GuiProcessTopologyDevTests(TestCase):
    def test_valid_tree_still_not_loaded_attestation(self):
        r=review(tree(),ROOT)
        self.assertTrue(r["expected_dev_process_tree_observed"])
        self.assertFalse(r["gui_runtime_attested"])
        self.assertFalse(r["activation_authorized"])
    def test_no_launcher_blocks(self):
        self.assertFalse(review(tree()[1:],ROOT)["expected_dev_process_tree_observed"])
    def test_wrong_parent_blocks(self):
        x=tree()
        x[-1]["ParentProcessId"]=55
        self.assertFalse(review(x,ROOT)["expected_dev_process_tree_observed"])
    def test_wrong_root_blocks(self):
        self.assertFalse(review(tree(),Path("C:/other"))["expected_dev_process_tree_observed"])
    def test_no_elevation_flag_required(self):
        x=tree()
        x[1]["CommandLine"]=x[1]["CommandLine"].replace("--no-elevate","")
        self.assertFalse(review(x,ROOT)["expected_dev_process_tree_observed"])
    def test_malformed_process_fails_closed(self):
        for bad in ({"ProcessId":True,"ParentProcessId":3,"CommandLine":"abc"},None,{}):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    review([bad],ROOT)
    def test_duplicate_pid_fails_closed(self):
        x=tree()+[tree()[0]]
        with self.assertRaises(ValueError):
            review(x,ROOT)
