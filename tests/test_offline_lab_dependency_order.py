import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rag.runtime.offline_lab_dependency_order import simulate_dependent_shutdown

class SyntheticDependencyTests(unittest.TestCase):
    def test_expected_order_is_only_lab_evidence(self):
        result=simulate_dependent_shutdown(active=("gui","mcp","adapter","indexer"))
        self.assertEqual(result["stop_order"],["gui","mcp","adapter","indexer"])
        self.assertEqual(result["state"],"LAB_ORDER_OBSERVED_UNPROVEN")
        self.assertFalse(result["copy_authorized"])
    def test_late_child_and_restart_fail_closed(self):
        result=simulate_dependent_shutdown(active=("gui","mcp"),late_children=("mcp",),restart_attempts=("gui",))
        self.assertEqual(result["state"],"BLOCKED")
        self.assertIn("LATE_CHILD:mcp",result["issues"])
        self.assertIn("RESTART_ATTEMPT:gui",result["issues"])
    def test_failed_stop_and_reconnect_fail_closed(self):
        result=simulate_dependent_shutdown(active=("mcp","adapter"),failed_services=("mcp",),reconnect_attempts=("adapter",))
        self.assertEqual(result["state"],"BLOCKED")
        self.assertIn("PRIMARY_STILL_ACTIVE",result["issues"])
        self.assertFalse(result["all_handles_closed"])
    def test_unknown_service_rejected(self):
        with self.assertRaises(ValueError):
            simulate_dependent_shutdown(active=("production-gui",))

if __name__=="__main__":
    unittest.main()
