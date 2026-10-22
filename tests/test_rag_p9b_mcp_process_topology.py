"""Synthetic read-only process topology regression."""
from pathlib import Path
import tempfile
import unittest
from installer.rag_p9b_mcp_process_topology import inspect_mcp_process_topology


class McpOwnershipTopologyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.installed=Path(self.temp.name)/"Programs"/"CodeBridge"
        self.installed.mkdir(parents=True)
        self.gui=str(self.installed/"app_rewrite/main.py")
        self.mcp=str(self.installed/"author_mcp/mcp_server.py")
        self.adapter=str(self.installed/"author_mcp/adapter_server.py")
        self.tunnel=str(self.installed/"tools/tunnel-client.exe")

    def x(self,pid,ppid,*cmd):
        return {"pid":pid,"ppid":ppid,"cmdline":list(cmd),"name":"python.exe"}

    def check(self,*items):
        return inspect_mcp_process_topology(self.installed,process_records=items)

    def test_gui_child_mcp_is_attached_but_not_authorized_for_stop(self):
        report=self.check(self.x(1,0,"pythonw.exe",self.gui),
                          self.x(2,1,"python.exe",self.mcp),
                          self.x(3,1,"python.exe",self.adapter),
                          self.x(4,1,self.tunnel,"run"))
        self.assertEqual(report["state"],"MCP_ATTACHED_TO_LIVE_GUI_OBSERVED")
        self.assertEqual(report["mcp_attached_to_gui"],[2])
        self.assertFalse(report["safe_to_stop_processes"])
        self.assertFalse(report["deployment_approved"])

    def test_missing_parent_mcp_is_not_assumed_managed_by_gui(self):
        report=self.check(self.x(1,5552,"pythonw.exe",self.gui),
                          self.x(2,10720,"python.exe",self.mcp),
                          self.x(3,1,"python.exe",self.adapter))
        self.assertEqual(report["state"],"MCP_INDEPENDENT_PROCESS_OWNERSHIP_UNVERIFIED")
        self.assertEqual(report["mcp_independent_of_current_gui"],[2])
        self.assertEqual(report["mcp_recorded_parent_absent"],[2])
        self.assertFalse(report["safe_to_stop_processes"])

    def test_parent_chain_with_intermediate_wrapper_detects_gui(self):
        report=self.check(self.x(1,0,"pythonw.exe",self.gui),
                          self.x(2,1,"wrapper.exe"),
                          self.x(3,2,"python.exe",self.mcp))
        self.assertEqual(report["mcp_attached_to_gui"],[3])

    def test_old_gui_and_current_gui_detached_mcp_refused(self):
        report=self.check(self.x(1,0,"pythonw.exe",self.gui),
                          self.x(2,4,"python.exe",self.mcp),
                          self.x(4,0,"foreign.exe"))
        self.assertEqual(report["state"],"MCP_INDEPENDENT_PROCESS_OWNERSHIP_UNVERIFIED")

    def test_system_idle_pid_zero_does_not_hide_valid_processes(self):
        report=self.check(self.x(0,0),self.x(1,0,"pythonw.exe",self.gui),
                          self.x(2,1,"python.exe",self.mcp))
        self.assertEqual(report["state"],"MCP_ATTACHED_TO_LIVE_GUI_OBSERVED")

    def test_no_mcp_is_not_proof_of_recovery(self):
        report=self.check(self.x(1,0,"pythonw.exe",self.gui))
        self.assertEqual(report["state"],"MCP_GUI_TOPOLOGY_INCOMPLETE")
        self.assertFalse(report["deployment_approved"])

    def test_wrong_install_script_is_not_mistaken_for_current_gui(self):
        report=self.check(self.x(1,0,"pythonw.exe",r"C:\Other\app_rewrite\main.py"),
                          self.x(2,1,"python.exe",self.mcp))
        self.assertEqual(report["state"],"MCP_GUI_TOPOLOGY_INCOMPLETE")

if __name__=="__main__":
    unittest.main()
