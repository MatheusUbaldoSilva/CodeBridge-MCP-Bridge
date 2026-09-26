import sys
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app_rewrite"

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from terminal_manager import TerminalManager
from ui import MainWindow


class FakeSession:
    def execute(
        self,
        command,
        on_output=None,
        prepared=False,
    ):
        return "ok"


class FakeTabs:
    def __init__(self, index=0):
        self.index = index
        self.changes = []
    def currentIndex(self):
        return self.index

    def setCurrentIndex(self, index):
        self.index = index
        self.changes.append(index)


class AutoSwapTests(unittest.TestCase):
    def test_execution_generation_increments(self):
        manager = TerminalManager.__new__(
            TerminalManager
        )
        manager._lock = threading.RLock()
        manager.active_target = None
        manager._prepared_target = "CMD"
        manager._execution_generation = 0
        manager._last_execution_target = None
        manager._ensure_session = (
            lambda target: FakeSession()
        )
        manager.announce = lambda *args: None

        result = manager.execute_prepared(
            "CMD",
            "echo ok",
        )

        self.assertEqual(result, "ok")
        self.assertEqual(
            manager._execution_generation,
            1,
        )
        self.assertEqual(
            manager._last_execution_target,
            "CMD",
        )

        manager.execute(
            "SSH",
            "echo ok",
        )

        self.assertEqual(
            manager._execution_generation,
            2,
        )
        self.assertEqual(
            manager._last_execution_target,
            "SSH",
        )

    def test_ui_swaps_once_per_generation(self):
        fake = type("FakeWindow", (), {})()
        fake._last_auto_swap_generation = 3
        fake.terminal_tab_indices = {
            "POWERSHELL5.1": 0,
            "CMD": 1,
            "SSH": 2,
        }
        fake.tabs = FakeTabs(index=0)

        terminals = {
            "execution_generation": 4,
            "last_execution_target": "SSH",
            "powershell": {"executing": False},
            "cmd": {"executing": False},
            "ssh": {"executing": True},
        }

        MainWindow._auto_swap_terminal_tab(
            fake,
            terminals,
        )
        self.assertEqual(fake.tabs.index, 2)
        self.assertEqual(fake.tabs.changes, [2])

        fake.tabs.index = 1
        MainWindow._auto_swap_terminal_tab(
            fake,
            terminals,
        )

        self.assertEqual(fake.tabs.index, 1)
        self.assertEqual(fake.tabs.changes, [2])

    def test_first_refresh_does_not_swap_old_execution(self):
        fake = type("FakeWindow", (), {})()
        fake._last_auto_swap_generation = None
        fake.terminal_tab_indices = {
            "POWERSHELL5.1": 0,
            "CMD": 1,
            "SSH": 2,
        }
        fake.tabs = FakeTabs(index=0)

        terminals = {
            "execution_generation": 8,
            "last_execution_target": "SSH",
            "powershell": {"executing": False},
            "cmd": {"executing": False},
            "ssh": {"executing": False},
        }

        MainWindow._auto_swap_terminal_tab(
            fake,
            terminals,
        )

        self.assertEqual(fake.tabs.index, 0)
        self.assertEqual(fake.tabs.changes, [])
        self.assertEqual(
            fake._last_auto_swap_generation,
            8,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
