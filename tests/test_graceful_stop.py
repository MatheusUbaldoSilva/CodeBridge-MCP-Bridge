import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app_rewrite"

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from chatgpt_companion import ChatGPTTimerState
from runtime import BridgeRuntime


class GracefulStopTests(unittest.TestCase):
    def make_runtime(self, active):
        runtime = BridgeRuntime.__new__(
            BridgeRuntime
        )
        runtime.chatgpt_timer = (
            ChatGPTTimerState()
        )
        runtime.chatgpt_timer.start(
            "test-request"
        )
        runtime.has_active_command = (
            lambda: bool(active)
        )
        return runtime

    def test_graceful_stop_requests_wrap_up(self):
        runtime = self.make_runtime(True)

        result = (
            runtime.request_graceful_stop()
        )
        control = (
            runtime.chatgpt_timer.turn_control()
        )

        self.assertTrue(
            result["requested"]
        )
        self.assertTrue(
            control["manual_request"]
        )
        self.assertTrue(
            control["request_wrap_up"]
        )
        self.assertEqual(
            control["stage"],
            "WRAP_UP_NOW",
        )
        self.assertEqual(
            control["action"],
            "FINISH_RESPONSE_NORMALLY",
        )

    def test_graceful_stop_without_active_command(self):
        runtime = self.make_runtime(False)

        result = (
            runtime.request_graceful_stop()
        )
        control = (
            runtime.chatgpt_timer.turn_control()
        )

        self.assertFalse(
            result["requested"]
        )
        self.assertEqual(
            result["reason"],
            "no_active_command",
        )
        self.assertFalse(
            control["manual_request"]
        )
        self.assertEqual(
            control["stage"],
            "INACTIVE",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
