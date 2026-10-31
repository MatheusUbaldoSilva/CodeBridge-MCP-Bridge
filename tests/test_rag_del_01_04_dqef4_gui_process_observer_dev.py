"""DQ-E-F-4 process topology is not module attestation."""
from pathlib import Path
from unittest import TestCase
from rag.runtime.knowledge_deletion_gui_process_observer_dev import review_gui_process_topology_dev as review
ROOT=Path("C:/Users/Matheus/CodeBridge-MCP-Bridge")
def tree():
    return [
        dict(ProcessId=10,ParentProcessId=1,
             CommandLine=r'"C:\Python\pythonw.exe" "C:\Users\Matheus\CodeBridge-Launcher\launcher.py"'),
        dict(ProcessId=20,ParentProcessId=10,CommandLine=r'"C:\Python\python.exe" "'+str(ROOT/"app_rewrite/main.py")+'" --no-elevate' ),
        dict(ProcessId=30,ParentProcessId=20,CommandLine=r'"C:\Python\python.exe" "'+str(ROOT/"author_mcp/mcp_server.py")+'" --host 127.0.0.1 --port 8765' ),
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


    def test_python_c_argument_cannot_impersonate_gui(self):
        x=tree()
        x[1]["CommandLine"]=r'"C:\Python\python.exe" -c "C:\Users\Matheus\CodeBridge-MCP-Bridge\app_rewrite\main.py --no-elevate"'
        self.assertFalse(review(x,ROOT)["expected_dev_process_tree_observed"])

    def test_unrelated_script_with_gui_path_as_flag_fails(self):
        x=tree()
        x[1]["CommandLine"]=(r'"C:\Python\python.exe" "C:\tmp\unrelated.py" '
                             +'"'+str(ROOT/"app_rewrite/main.py")+'" --no-elevate')
        self.assertFalse(review(x,ROOT)["expected_dev_process_tree_observed"])

    def test_mcp_port_text_without_real_argv_pair_fails(self):
        x=tree()
        x[2]["CommandLine"]=(r'"C:\Python\python.exe" "'+
            str(ROOT/"author_mcp/mcp_server.py")+'" "--port 8765"')
        self.assertFalse(review(x,ROOT)["expected_dev_process_tree_observed"])

    def test_gui_flag_must_be_exact(self):
        x=tree()
        x[1]["CommandLine"]=x[1]["CommandLine"].replace("--no-elevate",
                                                          "--no-elevate=1")
        self.assertFalse(review(x,ROOT)["expected_dev_process_tree_observed"])

    def test_launcher_path_must_be_exact(self):
        x=tree()
        x[0]["CommandLine"]=x[0]["CommandLine"].replace("launcher.py",
                                                          "launcher.py.backup")
        self.assertFalse(review(x,ROOT)["expected_dev_process_tree_observed"])

    def test_non_python_executable_cannot_claim_script(self):
        x=tree()
        x[1]["CommandLine"]=x[1]["CommandLine"].replace("python.exe",
                                                         "powershell.exe")
        self.assertFalse(review(x,ROOT)["expected_dev_process_tree_observed"])
