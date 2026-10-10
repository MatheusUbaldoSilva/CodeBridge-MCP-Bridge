"""End-to-end contract: collector evidence cannot assert full rollback."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from benchmarks.rag017_vm_windows_inventory import capture
from benchmarks.rag017_vm_evidence_compare import compare


class VMPipelineContractTests(unittest.TestCase):
    def test_scoped_collection_roundtrip_remains_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "CodeBridge-RAG017-VMTest-test"
            root.mkdir()
            (root / "canary.txt").write_text("before", encoding="utf-8")
            before_file = Path(temp) / "before.json"
            after_file = Path(temp) / "after.json"
            inventory = {"registry": {}, "shortcuts": {}, "services": {}}
            guest = {"Manufacturer": "Microsoft", "Model": "Virtual Machine"}
            with patch("benchmarks.rag017_vm_windows_inventory.guest_probe",
                       return_value=guest), patch(
                "benchmarks.rag017_vm_windows_inventory.subprocess.run",
                return_value=SimpleNamespace(stdout=json.dumps(inventory))):
                before = capture("vm-test", root, before_file)
                after = capture("vm-test", root, after_file)
            self.assertEqual(before["files"], after["files"])
            self.assertTrue(before["registry_inventory_collected"])
            self.assertFalse(before["registry_snapshot_verified"])
            self.assertFalse(before["vm_snapshot_verified"])
            result = compare(before, after)
            self.assertFalse(result["comparison_passed"])
            self.assertFalse(result["rollback_full_verified"])
            self.assertTrue(before_file.exists())
            self.assertTrue(after_file.exists())

    def test_changed_file_detected_without_snapshot_flags(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "CodeBridge-RAG017-VMTest-test"
            root.mkdir()
            target = root / "canary.txt"
            target.write_text("before", encoding="utf-8")
            inventory = {"registry": {}, "shortcuts": {}, "services": {}}
            guest = {"Manufacturer": "Microsoft", "Model": "Virtual Machine"}
            with patch("benchmarks.rag017_vm_windows_inventory.guest_probe",
                       return_value=guest), patch(
                "benchmarks.rag017_vm_windows_inventory.subprocess.run",
                return_value=SimpleNamespace(stdout=json.dumps(inventory))):
                before = capture("vm-test", root, Path(temp) / "before.json")
                target.write_text("after", encoding="utf-8")
                after = capture("vm-test", root, Path(temp) / "after.json")
            result = compare(before, after)
            self.assertTrue(result["differences_found"])
            self.assertEqual(result["differences"]["files"]["modified"], ["canary.txt"])
            self.assertFalse(result["rollback_full_verified"])


if __name__ == "__main__":
    unittest.main()
