import tempfile
import unittest
from pathlib import Path
from installer.rag_p9b_detached_process_ancestry import inspect_detached_process_ancestry


class FakeProcess:
    def __init__(self,pid,exe,command,parent=None):
        self.pid=pid
        self._exe=str(exe)
        self._command=list(map(str,command))
        self._parent=parent
    def exe(self):return self._exe
    def cmdline(self):return self._command
    def parent(self):return self._parent


class AncestryTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.installed=self.root/"CodeBridge"
        self.installed.mkdir()
        self.external=self.root/"external"
        self.external.mkdir()
        self.python=self.external/"python.exe"
        self.python.write_bytes(b"x")
        self.app=self.installed/"CodeBridge.exe"
        self.app.write_bytes(b"x")
    def assess(self,process):
        return inspect_detached_process_ancestry(installed=self.installed,process=process)
    def test_all_external_processes_verified(self):
        parent=FakeProcess(10,self.python,[self.python])
        child=FakeProcess(20,self.python,[self.python],parent)
        r=self.assess(child)
        self.assertEqual(r["state"],"EXTERNAL_PROCESS_ANCESTRY_VERIFIED")
        self.assertEqual(r["processes_inspected"],2)
        self.assertFalse(r["shutdown_authorized"])
    def test_parent_running_installed_app_refused(self):
        parent=FakeProcess(10,self.app,[self.app])
        child=FakeProcess(20,self.python,[self.python],parent)
        self.assertEqual(self.assess(child)["reason"],"PROCESS_INSIDE_INSTALLED_APP")
    def test_external_python_running_installed_script_refused(self):
        script=self.installed/"author_mcp.py"
        script.write_bytes(b"")
        child=FakeProcess(20,self.python,[self.python,script])
        self.assertEqual(self.assess(child)["reason"],"PROCESS_EXECUTES_INSTALLED_APP")
    def test_pid_cycle_refused(self):
        child=FakeProcess(20,self.python,[self.python])
        child._parent=child
        self.assertEqual(self.assess(child)["reason"],"INVALID_PROCESS_CHAIN")
    def test_unreadable_unknown_executable_still_refused(self):
        process=FakeProcess(20,self.python,[self.python])
        process.cmdline=lambda:(_ for _ in ()).throw(PermissionError("denied"))
        self.assertEqual(self.assess(process)["reason"],
                         "PROCESS_CMDLINE_UNAVAILABLE")

    def test_protected_windows_svchost_allows_denied_cmdline(self):
        import os
        system=Path(os.environ.get("WINDIR",r"C:\Windows"))/"System32"/"svchost.exe"
        if not system.is_file():
            self.skipTest("Windows System32 only")
        parent=FakeProcess(10,system,[])
        parent.cmdline=lambda:(_ for _ in ()).throw(PermissionError("denied"))
        child=FakeProcess(20,self.python,[self.python],parent)
        result=self.assess(child)
        self.assertEqual(result["state"],"EXTERNAL_PROCESS_ANCESTRY_VERIFIED")
        self.assertFalse(result["shutdown_authorized"])

    def test_nonexistent_executable_refused(self):
        child=FakeProcess(20,self.external/"missing.exe",[])
        self.assertEqual(self.assess(child)["reason"],"PROCESS_ANCESTRY_UNAVAILABLE")

if __name__=="__main__":unittest.main()
