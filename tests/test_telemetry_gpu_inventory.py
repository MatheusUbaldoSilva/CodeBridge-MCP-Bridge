import sys
import unittest
from pathlib import Path
from unittest.mock import patch

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
            }
        ]
        with patch.object(
            telemetry,
            "discover_windows_gpus",
            return_value=expected,
        ) as discover:
            service = telemetry.TelemetryService(
                config_store=object(),
                credential_store=object(),
            )

        self.assertEqual(
            service._gpu_inventory,
            expected,
        )
        discover.assert_called_once_with()


if __name__ == "__main__":
    unittest.main(verbosity=2)
