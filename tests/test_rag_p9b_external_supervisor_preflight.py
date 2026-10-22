"""Strict read-only process identity preflight."""
import tempfile
import unittest
from pathlib import Path

from installer.rag_p9b_external_supervisor_preflight import assess_external_supervisor,main
from unittest.mock import patch


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
        self.assertEqual(r["reason"],"OPAQUE_PROCESSES")
        self.assertEqual(r["opaque_processes"],1)
        self.assertFalse(r["safe_to_apply"])

    def test_known_active_processes_reported_even_with_opaque_windows_service(self):
        unknown=dict(pid=40,ppid=0,cmdline=None,create_time=2)
        r=self.check(self.proc(10,2,self.gui),
                     unknown,self.proc(20,3,self.mcp))
        self.assertEqual(r["state"],"SUPERVISOR_UPDATE_BLOCKED_RUNNING")
        self.assertEqual(r["opaque_processes"],1)
        self.assertEqual(r["blockers"],["GUI","MCP"])
        self.assertFalse(r["safe_to_apply"])

    def test_duplicate_pid_blocks(self):
        r=self.check(self.proc(10,2,self.gui),self.proc(10,3,self.mcp))
        self.assertEqual(r["reason"],"DUPLICATE_OR_INVALID_PID")

    def test_missing_mcp_parent_explicitly_reported(self):
        r=self.check(self.proc(10,1,self.gui,100.0),
                     self.proc(20,999,self.mcp,200.0))
        self.assertEqual(r["mcp_parent_absent"],[20])
        self.assertFalse(r["safe_to_apply"])

    def test_extra_script_path_not_matched(self):
        r=self.check(self.proc(10,2,self.gui+"-other.py"),
                     self.proc(20,3,self.mcp))
        self.assertEqual(r["state"],"SUPERVISOR_TOPOLOGY_INCOMPLETE")

    def test_missing_mcp_not_proof_of_shutdown(self):
        r=self.check(self.proc(10,2,self.gui))
        self.assertEqual(r["state"],"SUPERVISOR_TOPOLOGY_INCOMPLETE")
        self.assertFalse(r["safe_to_apply"])

    def test_cli_never_reports_success_when_live_stack_blocked(self):
        with patch("installer.rag_p9b_external_supervisor_preflight.assess_external_supervisor",
                   return_value={"state":"SUPERVISOR_UPDATE_BLOCKED_RUNNING"}):
            self.assertEqual(main(["--install-root",str(self.root)]),2)

    def test_nan_process_age_blocks(self):
        r=self.check(self.proc(10,2,self.gui,float("nan")))
        self.assertEqual(r["reason"],"PROCESS_CREATION_UNVERIFIED")


if __name__=="__main__":
    unittest.main()
