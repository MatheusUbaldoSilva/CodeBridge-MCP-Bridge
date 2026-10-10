import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmarks.rag017_vm_windows_inventory import capture, guest_identity


class VMInventoryTests(unittest.TestCase):
    def test_host_refused(self):
        self.assertFalse(guest_identity("LENOVO", "82X"))
        self.assertTrue(guest_identity("Microsoft Corporation", "Virtual Machine"))

    def test_never_collect_from_host(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "CodeBridge-RAG017-VMTest-canary"
            root.mkdir()
            out = Path(temp) / "evidence.json"
            with patch("benchmarks.rag017_vm_windows_inventory.guest_probe",
                       return_value={"Manufacturer": "LENOVO", "Model": "LOQ"}):
                with self.assertRaises(PermissionError):
                    capture("vm-a", root, out)
            self.assertFalse(out.exists())

    def test_existing_evidence_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "CodeBridge-RAG017-VMTest-canary"
            root.mkdir()
            out = Path(temp) / "evidence.json"
            out.write_text("CANARY")
            with patch("benchmarks.rag017_vm_windows_inventory.guest_probe",
                       return_value={"Manufacturer": "Microsoft", "Model": "Virtual Machine"}):
                with self.assertRaises(FileExistsError):
                    capture("vm-a", root, out)
            self.assertEqual(out.read_text(), "CANARY")

    def test_blank_vm_id_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "CodeBridge-RAG017-VMTest-canary"
            root.mkdir()
            with self.assertRaises(ValueError):
                capture("  ", root, Path(temp) / "out.json")

    def test_output_inside_scan_root_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "CodeBridge-RAG017-VMTest-canary"
            root.mkdir()
            with patch("benchmarks.rag017_vm_windows_inventory.guest_probe",
                       return_value={"Manufacturer": "Microsoft", "Model": "Virtual Machine"}):
                with self.assertRaises(ValueError):
                    capture("vm-a", root, root / "snapshot.json")
            self.assertFalse((root / "snapshot.json").exists())

    def test_wrong_root_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "wrong-root"
            root.mkdir()
            with patch("benchmarks.rag017_vm_windows_inventory.guest_probe",
                       return_value={"Manufacturer": "Microsoft", "Model": "Virtual Machine"}):
                with self.assertRaises(ValueError):
                    capture("vm-a", root, Path(temp) / "out.json")


if __name__ == "__main__":
    unittest.main()
