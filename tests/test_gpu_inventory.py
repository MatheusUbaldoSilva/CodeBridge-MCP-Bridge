import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app_rewrite"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import gpu_inventory


class FakeLuid:
    LowPart = 0x12345678
    HighPart = -1


class FakeDesc:
    Description = "Example GPU"
    VendorId = 0x10DE
    DeviceId = 0x25AC
    SubSysId = 0x3A6017AA
    Revision = 0xA1
    DedicatedVideoMemory = 6 * 1024**3
    DedicatedSystemMemory = 0
    SharedSystemMemory = 4 * 1024**3
    AdapterLuid = FakeLuid()
    Flags = 0


class GpuInventoryTests(unittest.TestCase):
    def test_adapter_record_preserves_identity_and_memory(self):
        record = gpu_inventory._adapter_record(
            2,
            FakeDesc(),
        )

        self.assertEqual(record["index"], 2)
        self.assertEqual(
            record["name"],
            "Example GPU",
        )
        self.assertEqual(
            record["vendor_id"],
            "10DE",
        )
        self.assertEqual(
            record["device_id"],
            "25AC",
        )
        self.assertEqual(
            record["subsystem_id"],
            "3A6017AA",
        )
        self.assertEqual(
            record["dedicated_vram_bytes"],
            6 * 1024**3,
        )
        self.assertEqual(
            record["shared_system_bytes"],
            4 * 1024**3,
        )
        self.assertEqual(
            record["luid"],
            "FFFFFFFF:12345678",
        )
        self.assertFalse(record["is_software"])

    def test_software_adapter_is_reported_not_hidden(self):
        desc = FakeDesc()
        desc.Flags = (
            gpu_inventory
            .DXGI_ADAPTER_FLAG_SOFTWARE
        )
        record = gpu_inventory._adapter_record(
            0,
            desc,
        )
        self.assertTrue(record["is_software"])

    def test_discovery_returns_empty_on_backend_failure(self):
        with patch.object(
            gpu_inventory,
            "_enumerate_dxgi_adapters",
            side_effect=OSError("dxgi failed"),
        ):
            self.assertEqual(
                gpu_inventory.discover_windows_gpus(),
                [],
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
