"""Strict read-only process identity preflight."""
import tempfile
import unittest
from pathlib import Path

from installer.rag_p9b_external_supervisor_preflight import assess_external_supervisor


class ExternalSupervisorPreflightTests(unittest.TestCase):
    def setUp(self):
        d=tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.root=Path(d.name)/"Programs"/"CodeBridge"
        self.root.mkdir(parents=True)
        self.gui=str(self.root/"app_rewrite"/"main.py")
        self.mcp=str(self.root/"author_mcp"/"mcp_server.py")

    def proc(self,pid,parent,path,created=100.0):
        return dict(pid=pid,ppid=parent,create_time=created,
                    cmdline=["python.exe",path],name="python.exe")

    def check(self,*records):
        return assess_external_supervisor(self.root,records=records)

    def test_both_live_are_blockers_not_permission(self):
        r=self.check(self.proc(10,2,self.gui),
                     self.proc(20,3,self.mcp))
        self.assertEqual(r["state"],"SUPERVISOR_UPDATE_BLOCKED_RUNNING")
        self.assertEqual(r["blockers"],["GUI","MCP"])
        self.assertFalse(r["safe_to_apply"])
        self.assertFalse(r["stop_authorized"])

    def test_unknown_creation_blocks(self):
        r=self.check(self.proc(10,2,self.gui),
                     self.proc(20,3,self.mcp,0.0))
        self.assertEqual(r["reason"],"PROCESS_CREATION_UNVERIFIED")

    def test_unreadable_cmdline_blocks(self):
        r=self.check(dict(pid=11,ppid=2,cmdline=None,create_time=1))
        self.assertEqual(r["reason"],"PROCESS_COMMANDLINE_UNAVAILABLE")

    def test_duplicate_pid_blocks(self):
        r=self.check(self.proc(10,2,self.gui),self.proc(10,3,self.mcp))
        self.assertEqual(r["reason"],"DUPLICATE_OR_INVALID_PID")

    def test_extra_script_path_not_matched(self):
        r=self.check(self.proc(10,2,self.gui+"-other.py"),
                     self.proc(20,3,self.mcp))
        self.assertEqual(r["state"],"SUPERVISOR_TOPOLOGY_INCOMPLETE")

    def test_missing_mcp_not_proof_of_shutdown(self):
        r=self.check(self.proc(10,2,self.gui))
        self.assertEqual(r["state"],"SUPERVISOR_TOPOLOGY_INCOMPLETE")
        self.assertFalse(r["safe_to_apply"])

    def test_nan_process_age_blocks(self):
        r=self.check(self.proc(10,2,self.gui,float("nan")))
        self.assertEqual(r["reason"],"PROCESS_CREATION_UNVERIFIED")


if __name__=="__main__":
    unittest.main()
