"""Synthetic only: no OS process can ever be stopped by this test."""
import tempfile
import unittest
from pathlib import Path
from installer.rag_p9b_shutdown_sequence import rehearse_shutdown_sequence


class FakeController:
    simulation_only=True

    def __init__(self, reject=None):
        self.calls=[]
        self.reject=reject

    def simulate_stop(self, role, pid, created):
        self.calls.append((role,pid,created))
        return role!=self.reject


class ShutdownSequenceTests(unittest.TestCase):
    def setUp(self):
        d=tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.root=Path(d.name)/"Programs"/"CodeBridge"
        self.root.mkdir(parents=True)

    def entry(self, kind,pid,parent,age):
        names=dict(GUI="app_rewrite/main.py",
                   MCP="author_mcp/mcp_server.py",
                   ADAPTER="author_mcp/adapter_server.py",
                   TUNNEL="tools/tunnel-client.exe")
        return dict(pid=pid,ppid=parent,create_time=age,
                    cmdline=["python.exe",str(self.root/names[kind])])

    def records(self):
        return [self.entry("GUI",10,1,100),
                self.entry("MCP",20,999,200),
                self.entry("ADAPTER",30,10,110),
                self.entry("TUNNEL",40,10,120)]

    def test_explicit_simulator_runs_expected_order(self):
        c=FakeController()
        r=rehearse_shutdown_sequence(self.root,records=self.records(),
                                     controller=c,simulate=True)
        self.assertEqual(r["state"],"SIMULATED_SEQUENCE_PASS")
        self.assertEqual([x[0] for x in c.calls],
                         ["GUI","MCP","ADAPTER","TUNNEL"])
        self.assertFalse(r["real_signals_sent"])
        self.assertFalse(r["deployment_approved"])

    def test_default_never_runs(self):
        c=FakeController()
        r=rehearse_shutdown_sequence(self.root,records=self.records(),
                                     controller=c)
        self.assertEqual(r["reason"],"SIMULATOR_REQUIRED")
        self.assertEqual(c.calls,[])

    def test_live_controller_is_refused(self):
        c=FakeController()
        c.simulation_only=False
        r=rehearse_shutdown_sequence(self.root,records=self.records(),
                                     controller=c,simulate=True)
        self.assertEqual(r["reason"],"NON_SIMULATION_CONTROLLER")
        self.assertEqual(c.calls,[])

    def test_failure_stops_remaining_simulated_steps(self):
        c=FakeController(reject="MCP")
        r=rehearse_shutdown_sequence(self.root,records=self.records(),
                                     controller=c,simulate=True)
        self.assertEqual(r["state"],"SIMULATED_SEQUENCE_ABORTED")
        self.assertEqual([x[0] for x in c.calls],["GUI","MCP"])

    def test_missing_process_refuses_simulation(self):
        c=FakeController()
        r=rehearse_shutdown_sequence(self.root,records=self.records()[:-1],
                                     controller=c,simulate=True)
        self.assertEqual(r["reason"],"INVALID_SHUTDOWN_PLAN")
        self.assertEqual(c.calls,[])


if __name__=="__main__":
    unittest.main()
