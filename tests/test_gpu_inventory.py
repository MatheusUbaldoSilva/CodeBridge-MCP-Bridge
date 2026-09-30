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


class GpuDeviceModelTests(unittest.TestCase):
    @staticmethod
    def record(
        *,
        index,
        name,
        vendor_id,
        dedicated,
        shared,
        software=False,
        luid=None,
    ):
        return {
            "index": index,
            "name": name,
            "vendor_id": vendor_id,
            "device_id": "0001",
            "subsystem_id": "00000000",
            "revision": 1,
            "dedicated_vram_bytes": dedicated,
            "dedicated_system_bytes": 0,
            "shared_system_bytes": shared,
            "luid": (
                luid
                or f"00000000:{index:08X}"
            ),
            "is_software": software,
        }

    def test_known_vendor_and_integrated_classification(self):
        device = gpu_inventory.GPUDevice.from_record(
            self.record(
                index=0,
                name="Intel Integrated",
                vendor_id="8086",
                dedicated=128 * 1024**2,
                shared=4 * 1024**3,
            )
        )

        self.assertEqual(
            device.vendor_name,
            "Intel",
        )
        self.assertTrue(device.is_integrated)
        self.assertFalse(device.is_discrete)
        self.assertEqual(
            device.adapter_type,
            "integrated",
        )

    def test_unknown_vendor_remains_valid_device(self):
        device = gpu_inventory.GPUDevice.from_record(
            self.record(
                index=0,
                name="Future GPU",
                vendor_id="ABCD",
                dedicated=8 * 1024**3,
                shared=2 * 1024**3,
            )
        )

        self.assertEqual(
            device.vendor_name,
            "Unknown",
        )
        self.assertEqual(
            device.vendor_id,
            "ABCD",
        )
        self.assertTrue(device.is_discrete)

    def test_primary_prefers_discrete_hardware_over_integrated_and_software(self):
        records = [
            self.record(
                index=0,
                name="Integrated GPU",
                vendor_id="8086",
                dedicated=128 * 1024**2,
                shared=4 * 1024**3,
            ),
            self.record(
                index=1,
                name="Discrete GPU",
                vendor_id="10DE",
                dedicated=6 * 1024**3,
                shared=4 * 1024**3,
            ),
            self.record(
                index=2,
                name="Software Adapter",
                vendor_id="1414",
                dedicated=0,
                shared=4 * 1024**3,
                software=True,
            ),
        ]

        devices = gpu_inventory.build_gpu_devices(
            records
        )
        primary = [
            device
            for device in devices
            if device.is_primary
        ]

        self.assertEqual(len(primary), 1)
        self.assertEqual(
            primary[0].name,
            "Discrete GPU",
        )
        self.assertEqual(
            primary[0].adapter_type,
            "discrete",
        )

    def test_primary_uses_hardware_when_only_integrated_and_software_exist(self):
        records = [
            self.record(
                index=0,
                name="Integrated GPU",
                vendor_id="8086",
                dedicated=128 * 1024**2,
                shared=4 * 1024**3,
            ),
            self.record(
                index=1,
                name="Software Adapter",
                vendor_id="1414",
                dedicated=0,
                shared=8 * 1024**3,
                software=True,
            ),
        ]

        devices = gpu_inventory.build_gpu_devices(
            records
        )
        primary = next(
            device
            for device in devices
            if device.is_primary
        )
        self.assertEqual(
            primary.name,
            "Integrated GPU",
        )

    def test_to_dict_exposes_generic_ui_contract(self):
        device = gpu_inventory.GPUDevice.from_record(
            self.record(
                index=3,
                name="AMD GPU",
                vendor_id="1002",
                dedicated=16 * 1024**3,
                shared=8 * 1024**3,
            )
        )
        data = device.to_dict()

        self.assertEqual(
            data["vendor_name"],
            "AMD",
        )
        self.assertEqual(
            data["adapter_type"],
            "discrete",
        )
        self.assertIn("is_primary", data)
        self.assertIn("is_integrated", data)
        self.assertIn("is_discrete", data)


if __name__ == "__main__":
    unittest.main(verbosity=2)
