import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rag.runtime.offline_lab_drain import LabDrain

class LabDrainTests(unittest.TestCase):
    def test_draining_denies_new_work_and_ack_after_existing_finishes(self):
        gate=LabDrain()
        self.assertTrue(gate.start())
        self.assertTrue(gate.request_drain())
        self.assertFalse(gate.start())
        self.assertFalse(gate.report()["drain_ack"])
        gate.finish()
        self.assertTrue(gate.report()["drain_ack"])
        self.assertFalse(gate.report()["copy_authorized"])
        self.assertTrue(gate.abort())
        self.assertTrue(gate.start())
    def test_timeout_requires_explicit_abort(self):
        gate=LabDrain(active=2)
        gate.request_drain()
        self.assertTrue(gate.timeout())
        self.assertFalse(gate.start())
        self.assertFalse(gate.report()["drain_ack"])
        self.assertTrue(gate.abort())
        self.assertTrue(gate.report()["new_requests_allowed"])
    def test_fail_closed_invalid_inputs(self):
        with self.assertRaises(ValueError): LabDrain(active=-1)
        with self.assertRaises(ValueError): LabDrain(active=True)
        with self.assertRaises(ValueError): LabDrain().finish()
    def test_empty_drain_still_not_backup_authorized(self):
        gate=LabDrain()
        gate.request_drain()
        result=gate.report()
        self.assertTrue(result["drain_ack"])
        self.assertFalse(result["production_quiescence_proven"])
        self.assertFalse(result["copy_authorized"])

if __name__=="__main__":
    unittest.main()
