"""Synthetic post-shutdown probes without touching live processes."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from installer.rag_p9b_poststop_verification import check_poststop, main
from unittest.mock import patch


class PostStopChecks(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=Path(t.name)/"Programs"/"CodeBridge"
        self.root.mkdir(parents=True)

    def run_probe(self, records, ports=lambda host, port: False):
        official=[SimpleNamespace(info={
            "pid":item["pid"],"cmdline":item.get("cmdline") or []
        }) for item in records]
        return check_poststop(self.root,process_records=records,
                              official_processes=iter(official),
                              port_probe=ports)

    def proc(self,script,pid=20):
        return {"pid":pid,"ppid":1,"create_time":100.0,
                "cmdline":["python.exe",str(self.root/script)]}

    def test_cli_never_signals_apply_authorization(self):
        with patch("installer.rag_p9b_poststop_verification.check_poststop",
                   return_value={"state":"POSTSTOP_OBSERVED_ONLY"}):
            self.assertEqual(main(["--install-root",str(self.root)]),2)

    def test_no_processes_and_no_listener_is_only_observation(self):
        r=self.run_probe([])
        self.assertEqual(r["state"],"POSTSTOP_OBSERVED_ONLY")
        self.assertTrue(r["observed_stopped"])
        self.assertFalse(r["installer_launch_authorized"])

    def test_mcp_running_blocks(self):
        r=self.run_probe([self.proc(Path("author_mcp/mcp_server.py"))])
        self.assertEqual(r["reason"],"CODEBRIDGE_PROCESSES_STILL_RUNNING")

    def test_gui_running_blocks(self):
        r=self.run_probe([self.proc(Path("app_rewrite/main.py"))])
        self.assertEqual(r["reason"],"CODEBRIDGE_PROCESSES_STILL_RUNNING")

    def test_mcp_port_blocks(self):
        r=self.run_probe([],ports=lambda h,p: p==8765)
        self.assertEqual(r["reason"],"MCP_LISTENER_STILL_ONLINE")

    def test_unknown_port_fails_closed(self):
        def broken(h,p):
            raise OSError("can't inspect")
        r=self.run_probe([],ports=broken)
        self.assertEqual(r["reason"],"PORT_STATE_UNVERIFIED")

    def test_unrelated_opaque_windows_service_does_not_block(self):
        records=[{"pid":40,"ppid":1,"name":"svchost.exe",
                  "cmdline":None,"create_time":100}]
        r=self.run_probe(records)
        self.assertEqual(r["state"],"POSTSTOP_OBSERVED_ONLY")
        self.assertFalse(r["installer_launch_authorized"])

    def test_empty_python_cmdline_fails_closed(self):
        r=self.run_probe([{"pid":41,"ppid":1,"name":"python.exe",
                          "cmdline":[],"create_time":100}])
        self.assertEqual(r["reason"],"OPAQUE_PROCESS_IDENTITY")

    def test_inaccessible_process_fails_closed(self):
        r=self.run_probe([{"pid":40,"ppid":1,"name":"python.exe",
                          "cmdline":None,"create_time":100}])
        self.assertEqual(r["reason"],"OPAQUE_PROCESS_IDENTITY")


if __name__=="__main__":
    unittest.main()
