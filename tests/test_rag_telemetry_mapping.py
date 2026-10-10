"""Verify telemetry follows the actual selected tab, not index thresholds."""
import os
import sys
import unittest
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app_rewrite"))
from PySide6.QtWidgets import QApplication, QTabWidget, QStackedWidget, QWidget
from ui import MainWindow

class TelemetryMappingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_ssh_and_rag_mapping(self):
        class Fake:
            pass
        fake = Fake()
        fake.tabs = QTabWidget()
        tabs = [QWidget() for _ in range(5)]
        for item in tabs:
            fake.tabs.addTab(item, "test")
        fake.ssh_tab = tabs[3]
        fake.terminal_tab_indices = {"SSH": 2}
        fake.telemetry_stack = QStackedWidget()
        fake.telemetry_windows = QWidget()
        fake.telemetry_linux = QWidget()
        fake.telemetry_stack.addWidget(fake.telemetry_windows)
        fake.telemetry_stack.addWidget(fake.telemetry_linux)
        for index in range(5):
            MainWindow._sync_telemetry_panel(fake, index)
            expected = fake.telemetry_linux if index in (2, 3) else fake.telemetry_windows
            self.assertIs(fake.telemetry_stack.currentWidget(), expected)

if __name__ == "__main__":
    unittest.main()
