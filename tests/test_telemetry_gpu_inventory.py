import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app_rewrite"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import telemetry


class GpuInventoryTelemetryTests(unittest.TestCase):
    def test_service_captures_gpu_inventory_once(self):
        expected = [
            {
                "index": 0,
                "name": "Example GPU",
                "vendor_id": "1234",
                "device_id": "5678",
                "is_primary": True,
            }
        ]
        fake_provider = Mock()
        with (
            patch.object(
                telemetry,
                "discover_windows_gpus",
                return_value=expected,
            ) as discover,
            patch.object(
                telemetry,
                "WindowsGpuTelemetry",
                return_value=fake_provider,
            ) as provider,
        ):
            service = telemetry.TelemetryService(
                config_store=object(),
                credential_store=object(),
            )

        self.assertEqual(
            service._gpu_inventory,
            expected,
        )
        self.assertEqual(
            service._primary_gpu,
            expected[0],
        )
        discover.assert_called_once_with()
        provider.assert_called_once_with(expected)
        self.assertIs(
            service._gpu_telemetry,
            fake_provider,
        )

    def test_stop_closes_generic_gpu_provider(self):
        fake_provider = Mock()
        with (
            patch.object(
                telemetry,
                "discover_windows_gpus",
                return_value=[],
            ),
            patch.object(
                telemetry,
                "WindowsGpuTelemetry",
                return_value=fake_provider,
            ),
        ):
            service = telemetry.TelemetryService(
                config_store=object(),
                credential_store=object(),
            )

        service.stop()

        fake_provider.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main(verbosity=2)
