import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rag.runtime.offline_scoped_cim_observer import observe_scoped_windows_pids
from rag.runtime.offline_lab_drain import LabDrain
from rag.runtime.offline_lab_dependency_order import simulate_dependent_shutdown

class LabFailureInjectionTests(unittest.TestCase):
    def test_drain_timeout_and_unhandled_work_block(self):
        state=LabDrain(active=1)
        state.request_drain()
        self.assertTrue(state.timeout())
        result=state.report()
        self.assertFalse(result["drain_ack"])
        self.assertFalse(result["copy_authorized"])

    def test_lost_ipc_and_observer_exception_fail_closed(self):
        def gone(*args,**kwargs):
            raise subprocess.TimeoutExpired(cmd="powershell.exe",timeout=1)
        report=observe_scoped_windows_pids([123],runner=gone)
        self.assertEqual(report["state"],"BLOCKED")
        self.assertFalse(report["identity_inventory_ok"])
        self.assertFalse(report["production_quiescence_proven"])

    def test_nine_unverifiable_processes_never_establish_quiescence(self):
        pids=list(range(1001,1010))
        report=observe_scoped_windows_pids(pids,runner=lambda *args,**kwargs:SimpleNamespace(stdout='[]'))
        self.assertEqual(report["state"],"SCOPED_CIM_OBSERVATION_UNPROVEN")
        self.assertEqual(report["verified_pids"],[])
        self.assertFalse(report["copy_authorized"])
        self.assertFalse(report["all_handles_closed"])

    def test_crash_restart_and_unexpected_service_fail_closed(self):
        result=simulate_dependent_shutdown(active=("gui","mcp","adapter"),
            failed_services=("mcp",),restart_attempts=("adapter",),
            late_children=("gui",))
        self.assertEqual(result["state"],"BLOCKED")
        self.assertTrue(result["issues"])
        self.assertFalse(result["copy_authorized"])
        with self.assertRaises(ValueError):
            simulate_dependent_shutdown(active=("unexpected-process",))

if __name__=="__main__":
    unittest.main()
