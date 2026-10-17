import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rag.runtime.offline_external_lab_supervisor import run_external_synthetic_observer

class ExternalSupervisorLabTests(unittest.TestCase):
    def test_cooperative_child_exit_is_not_production_authorization(self):
        result=run_external_synthetic_observer()
        self.assertEqual(result["state"],"LAB_COOPERATIVE_EXIT_OBSERVED_UNPROVEN")
        self.assertTrue(result["exit_observed"])
        self.assertTrue(result["cooperative_stop"])
        self.assertIsInstance(result["child_pid"],int)
        self.assertFalse(result["copy_authorized"])
        self.assertFalse(result["all_handles_closed"])
        self.assertFalse(result["production_quiescence_proven"])

    def test_invalid_timeout_fails_before_launch(self):
        for timeout in (0, -1, 21, True, "abc"):
            with self.subTest(timeout=timeout):
                with self.assertRaises(ValueError):
                    run_external_synthetic_observer(timeout=timeout)

if __name__=="__main__":
    unittest.main()
