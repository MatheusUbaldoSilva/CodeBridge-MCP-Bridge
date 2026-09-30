import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app_rewrite"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from PySide6.QtWidgets import QApplication

from telemetry_widget import (
    TelemetryPanel,
    _gpu_view,
)


class FakeBar:
    def __init__(self):
        self.value = None
        self.text = None

    def setValue(self, value):
        self.value = value

    def setFormat(self, text):
        self.text = text


class GpuViewTests(unittest.TestCase):
    def test_enriched_primary_drives_all_visible_gpu_values(self):
        data = {
            "gpu_telemetry": {
                "primary": {
                    "name": "Example GPU",
                    "percent": 37.4,
                    "temperature_c": 58.0,
                    "vram_used_bytes": (
                        2 * 1024**3
                    ),
                    "vram_total_bytes": (
                        8 * 1024**3
                    ),
                    "vram_percent": 25.0,
                }
            }
        }

        view = _gpu_view(data)

        self.assertEqual(
            view["name"],
            "Example GPU",
        )
        self.assertEqual(
            view["gpu_percent"],
            37.4,
        )
        self.assertEqual(
            view["temperature_text"],
            "58 \u00b0C",
        )
        self.assertEqual(
            view["vram_percent"],
            25.0,
        )
        self.assertEqual(
            view["vram_used_bytes"],
            2 * 1024**3,
        )
        self.assertEqual(
            view["vram_total_bytes"],
            8 * 1024**3,
        )

    def test_missing_temperature_is_nd_not_zero_degrees(self):
        data = {
            "gpu_telemetry": {
                "primary": {
                    "name": "Generic GPU",
                    "percent": 12.0,
                    "temperature_c": None,
                    "vram_used_bytes": 100,
                    "vram_total_bytes": 400,
                    "vram_percent": None,
                }
            }
        }

        view = _gpu_view(data)

        self.assertEqual(
            view["temperature_text"],
            "N/D",
        )
        self.assertEqual(
            view["vram_percent"],
            25.0,
        )

    def test_inventory_fallback_keeps_unknown_metrics_visible(self):
        data = {
            "gpu_telemetry": {
                "primary": None,
                "error": "counter unavailable",
            },
            "primary_gpu": {
                "name": "Future GPU",
                "dedicated_vram_bytes": (
                    12 * 1024**3
                ),
            },
        }

        view = _gpu_view(data)

        self.assertEqual(
            view["name"],
            "Future GPU",
        )
        self.assertIsNone(
            view["gpu_percent"]
        )
        self.assertEqual(
            view["temperature_text"],
            "N/D",
        )
        self.assertIsNone(
            view["vram_used_bytes"]
        )
        self.assertEqual(
            view["vram_total_bytes"],
            12 * 1024**3,
        )
        self.assertIsNone(
            view["vram_percent"]
        )

    def test_no_detected_gpu_returns_none(self):
        self.assertIsNone(
            _gpu_view({})
        )

    def test_optional_bar_renders_unknown_as_nd(self):
        bar = FakeBar()

        TelemetryPanel._set_optional_bar(
            bar,
            None,
        )

        self.assertEqual(bar.value, 0)
        self.assertEqual(bar.text, "N/D")

    def test_optional_bar_renders_percentage(self):
        bar = FakeBar()

        TelemetryPanel._set_optional_bar(
            bar,
            42.6,
        )

        self.assertEqual(bar.value, 43)
        self.assertEqual(bar.text, "43%")


class FakeTelemetryService:
    def set_interval(self, value):
        self.interval = value

    def snapshot(self, kind):
        return {
            "online": True,
            "cpu_percent": 0,
            "ram_percent": 0,
            "disk_percent": 0,
            "gpu_telemetry": {},
            "primary_gpu": None,
        }


class MonitorSystemHeaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = (
            QApplication.instance()
            or QApplication([])
        )

    def test_header_is_fixed_monitor_system_without_collapse_control(self):
        panel = TelemetryPanel(
            FakeTelemetryService(),
            "windows",
        )
        try:
            self.assertEqual(
                panel.title_label.text(),
                "MONITOR DO SISTEMA",
            )
            self.assertFalse(
                hasattr(panel, "toggle_button")
            )
            self.assertFalse(
                hasattr(panel, "_collapsed")
            )
            self.assertFalse(
                hasattr(panel, "toggle")
            )
            self.assertEqual(
                panel.minimumWidth(),
                270,
            )
            self.assertEqual(
                panel.maximumWidth(),
                300,
            )
            self.assertFalse(
                panel.body.isHidden()
            )
        finally:
            panel.deleteLater()


if __name__ == "__main__":
    unittest.main(verbosity=2)
