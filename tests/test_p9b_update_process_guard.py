"""Read-only tests of the CodeBridge GUI/MCP updater process gate."""
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace

from installer.p9b_update_process_guard import inspect_update_processes


class UpdaterProcessGateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.installed=Path(self.temp.name)/"Programs"/"CodeBridge"
        self.installed.mkdir(parents=True)
        self.gui=str(self.installed/"app_rewrite"/"main.py")
        self.mcp=str(self.installed/"author_mcp"/"mcp_server.py")

    def p(self,pid,*cmdline):
        return SimpleNamespace(info={
            "pid":pid,"name":"python.exe","cmdline":list(cmdline),
        })

    def check(self,*procs):
        return inspect_update_processes(self.installed,process_iter=iter(procs))

    def test_gui_process_prevents_update(self):
        r=self.check(self.p(1,"pythonw.exe",self.gui))
        self.assertEqual(r["state"],"UPDATE_PROCESS_BLOCKED")
        self.assertEqual(r["blockers"],["CODEBRIDGE_GUI_RUNNING"])
        self.assertFalse(r["installer_launch_authorized"])

    def test_mcp_process_prevents_update_even_without_gui(self):
        r=self.check(self.p(2,"python.exe",self.mcp,"--port","8765"))
        self.assertIn("CODEBRIDGE_MCP_RUNNING",r["blockers"])
        self.assertFalse(r["processes_stopped"])

    def test_both_running_are_detected(self):
        r=self.check(self.p(1,"pythonw.exe",self.gui),
                     self.p(2,"python.exe",self.mcp))
        self.assertEqual(r["blockers"],[
            "CODEBRIDGE_GUI_RUNNING","CODEBRIDGE_MCP_RUNNING",
        ])

    def test_other_python_programs_are_not_mistaken_for_codebridge(self):
        r=self.check(self.p(3,"python.exe",r"C:\Another\main.py"),
                     self.p(4,"python.exe",r"C:\Another\mcp_server.py"))
        self.assertEqual(r["state"],"NO_RUNNING_CODEBRIDGE")
        self.assertEqual(r["blockers"],[])
        self.assertFalse(r["installer_launch_authorized"])

    def test_unknown_process_information_denied(self):
        inaccessible=SimpleNamespace(info={"pid":5,"cmdline":[]})
        class Fault:
            @property
            def info(self):
                raise PermissionError("synthetic access denied")
        r=self.check(inaccessible,Fault())
        self.assertEqual(r["state"],"UPDATE_PROCESS_UNVERIFIED")
        self.assertIn("PROCESS_ACCESS_UNVERIFIED",r["blockers"])

    def test_nonexistent_root_denied(self):
        r=inspect_update_processes(self.installed/"nonexistent",
                                   process_iter=iter(()))
        self.assertEqual(r["state"],"UPDATE_PROCESS_UNVERIFIED")

    def test_foreign_same_filename_does_not_block(self):
        foreign=r"C:\OtherApp\CodeBridge\author_mcp\mcp_server.py"
        r=self.check(self.p(10,"python.exe",foreign))
        self.assertEqual(r["state"],"NO_RUNNING_CODEBRIDGE")


if __name__=="__main__":
    unittest.main()
