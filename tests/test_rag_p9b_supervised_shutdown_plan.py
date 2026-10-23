"""Dry-run supervisor identity contract."""
import tempfile
import unittest
from pathlib import Path

from installer.rag_p9b_supervised_shutdown_plan import make_shutdown_plan, main
from unittest.mock import patch


class ShutdownPlanTests(unittest.TestCase):
    def setUp(self):
        d=tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.root=Path(d.name)/"Programs"/"CodeBridge"
        self.root.mkdir(parents=True)

    def item(self, kind, pid, parent=1, age=100.0):
        scripts={
            "GUI":self.root/"app_rewrite"/"main.py",
            "MCP":self.root/"author_mcp"/"mcp_server.py",
            "ADAPTER":self.root/"author_mcp"/"adapter_server.py",
            "TUNNEL":self.root/"tools"/"tunnel-client.exe",
        }
        return dict(pid=pid,ppid=parent,create_time=age,
                    cmdline=["python.exe",str(scripts[kind])])

    def valid(self):
        return [self.item("GUI",10,1,100),
                self.item("MCP",20,999,200),
                self.item("ADAPTER",30,10,110),
                self.item("TUNNEL",40,10,120)]

    def test_cli_never_grants_installer_green_light(self):
        with patch("installer.rag_p9b_supervised_shutdown_plan.make_shutdown_plan",
                   return_value={"state":"SHUTDOWN_PLAN_ONLY"}):
            self.assertEqual(main(["--install-root",str(self.root)]),2)

    def test_dry_run_four_roles(self):
        r=make_shutdown_plan(self.root,records=self.valid())
        self.assertEqual(r["state"],"SHUTDOWN_PLAN_ONLY")
        self.assertEqual(len(r["processes"]),4)
        self.assertEqual(len(r["identity_digest"]),64)
        self.assertFalse(r["signals_sent"])
        self.assertFalse(r["safe_to_apply_installer"])

    def test_plan_independent_of_enumeration_order(self):
        a=self.valid()
        b=list(reversed(a))
        self.assertEqual(
            make_shutdown_plan(self.root,records=a)["identity_digest"],
            make_shutdown_plan(self.root,records=b)["identity_digest"])

    def test_unexpected_duplicate_mcp_blocks(self):
        r=make_shutdown_plan(self.root,records=self.valid()+[
            self.item("MCP",55,800,220)])
        self.assertEqual(r["reason"],"UNEXPECTED_PROCESS_MULTIPLICITY")

    def test_gui_owned_mcp_accepted_for_shutdown_plan_only(self):
        r=self.valid()
        r[1]["ppid"]=10
        result=make_shutdown_plan(self.root,records=r)
        self.assertEqual(result["state"],"SHUTDOWN_PLAN_ONLY")
        self.assertFalse(result["safe_to_apply_installer"])

    def test_unexpected_attached_mcp_blocks(self):
        r=self.valid()
        r[1]["ppid"]=30
        result=make_shutdown_plan(self.root,records=r)
        self.assertEqual(result["reason"],"UNEXPECTED_MCP_ANCESTRY")

    def test_missing_role_blocks(self):
        r=make_shutdown_plan(self.root,records=self.valid()[:-1])
        self.assertEqual(r["reason"],"UNEXPECTED_PROCESS_MULTIPLICITY")

    def test_bad_identity_blocks(self):
        r=self.valid()
        r[1]["create_time"]=0
        result=make_shutdown_plan(self.root,records=r)
        self.assertEqual(result["reason"],"TOPOLOGY_UNVERIFIED")


if __name__=="__main__":
    unittest.main()
