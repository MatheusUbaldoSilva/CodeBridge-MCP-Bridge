import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app_rewrite"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from gpu_telemetry_windows import (
    _aggregate_engine_usage,
    _aggregate_memory_usage,
    _luid_from_instance,
    build_gpu_metrics,
)


LUID = "00000000:0000C350"


def engine_name(pid, engine):
    return (
        f"pid_{pid}_"
        "luid_0x00000000_0x0000C350_"
        f"phys_0_eng_{engine}_engtype_3D"
    )


def memory_name():
    return (
        "luid_0x00000000_0x0000C350_"
        "phys_0"
    )


class WindowsGpuTelemetryTests(unittest.TestCase):
    def test_extracts_luid_from_windows_counter_instance(self):
        self.assertEqual(
            _luid_from_instance(
                engine_name(10, 0)
            ),
            LUID,
        )

    def test_engine_usage_sums_processes_per_engine_and_uses_busiest_engine(self):
        samples = [
            {
                "name": engine_name(10, 0),
                "value": 20.0,
            },
            {
                "name": engine_name(20, 0),
                "value": 30.0,
            },
            {
                "name": engine_name(30, 1),
                "value": 70.0,
            },
        ]

        result = _aggregate_engine_usage(
            samples
        )

        self.assertEqual(
            result[LUID],
            70.0,
        )

    def test_engine_usage_caps_each_engine_at_100_percent(self):
        samples = [
            {
                "name": engine_name(10, 0),
                "value": 70.0,
            },
            {
                "name": engine_name(20, 0),
                "value": 50.0,
            },
        ]

        result = _aggregate_engine_usage(
            samples
        )

        self.assertEqual(
            result[LUID],
            100.0,
        )

    def test_memory_usage_sums_matching_instances(self):
        result = _aggregate_memory_usage(
            [
                {
                    "name": memory_name(),
                    "value": 100.0,
                },
                {
                    "name": memory_name(),
                    "value": 200.0,
                },
            ]
        )

        self.assertEqual(
            result[LUID],
            300.0,
        )

    def test_build_metrics_calculates_vram_percent(self):
        total = 8 * 1024**3
        used = 2 * 1024**3
        devices = [
            {
                "index": 1,
                "luid": LUID,
                "name": "Example GPU",
                "vendor_id": "ABCD",
                "vendor_name": "Unknown",
                "adapter_type": "discrete",
                "is_primary": True,
                "dedicated_vram_bytes": total,
                "shared_system_bytes": (
                    4 * 1024**3
                ),
            }
        ]

        result = build_gpu_metrics(
            devices,
            [
                {
                    "name": engine_name(10, 0),
                    "value": 42.0,
                }
            ],
            [
                {
                    "name": memory_name(),
                    "value": used,
                }
            ],
            [
                {
                    "name": memory_name(),
                    "value": 256 * 1024**2,
                }
            ],
        )
        primary = result["primary"]

        self.assertEqual(
            primary["percent"],
            42.0,
        )
        self.assertEqual(
            primary["vram_used_bytes"],
            used,
        )
        self.assertEqual(
            primary["vram_total_bytes"],
            total,
        )
        self.assertAlmostEqual(
            primary["vram_percent"],
            25.0,
        )
        self.assertIsNone(
            primary["temperature_c"]
        )
        self.assertEqual(
            primary["telemetry_source"],
            "windows_pdh",
        )

    def test_zero_dedicated_vram_reports_unknown_vram_percent(self):
        devices = [
            {
                "index": 0,
                "luid": LUID,
                "name": "Integrated GPU",
                "vendor_id": "8086",
                "vendor_name": "Intel",
                "adapter_type": "integrated",
                "is_primary": True,
                "dedicated_vram_bytes": 0,
                "shared_system_bytes": (
                    8 * 1024**3
                ),
            }
        ]

        result = build_gpu_metrics(
            devices,
            [],
            [],
            [],
        )

        self.assertIsNone(
            result["primary"]["vram_percent"]
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
