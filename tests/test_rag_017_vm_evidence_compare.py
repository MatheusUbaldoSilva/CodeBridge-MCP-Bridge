import copy
import unittest

from benchmarks.rag017_vm_evidence_compare import compare, FLAGS, SECTIONS


class RollbackEvidenceCompareTests(unittest.TestCase):
    def complete(self):
        result = {"vm_id": "vm-rag017-disposable", "root": "C:/CodeBridge-RAG017-VMTest-test"}
        result.update({flag: True for flag in FLAGS})
        result.update({section: {"sample": "hash1"} for section in SECTIONS})
        return result

    def test_equal_snapshots_only_pass_comparison(self):
        snapshot = self.complete()
        result = compare(snapshot, copy.deepcopy(snapshot))
        self.assertTrue(result["comparison_passed"])
        self.assertFalse(result["rollback_full_verified"])

    def test_changed_registry_detected(self):
        before = self.complete()
        after = copy.deepcopy(before)
        after["registry"]["sample"] = "different"
        result = compare(before, after)
        self.assertFalse(result["comparison_passed"])
        self.assertEqual(result["differences"]["registry"]["modified"], ["sample"])

    def test_missing_section_fails_closed(self):
        before = self.complete()
        after = copy.deepcopy(before)
        del after["services"]
        self.assertFalse(compare(before, after)["comparison_passed"])

    def test_missing_hypervisor_proof_fails_closed(self):
        before = self.complete()
        after = copy.deepcopy(before)
        before["vm_snapshot_verified"] = False
        self.assertFalse(compare(before, after)["comparison_passed"])

    def test_different_roots_fail_closed(self):
        before = self.complete()
        after = copy.deepcopy(before)
        after["root"] = "C:/CodeBridge-RAG017-VMTest-other"
        result = compare(before, after)
        self.assertFalse(result["comparison_passed"])
        self.assertFalse(result["same_evidence_root"])

    def test_missing_root_fails_closed(self):
        before = self.complete()
        after = copy.deepcopy(before)
        del after["root"]
        self.assertFalse(compare(before, after)["comparison_passed"])

    def test_different_vm_fails_closed(self):
        before = self.complete()
        after = copy.deepcopy(before)
        after["vm_id"] = "another-vm"
        self.assertFalse(compare(before, after)["comparison_passed"])


if __name__ == "__main__":
    unittest.main()
