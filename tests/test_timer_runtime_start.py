import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app_rewrite"

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from chatgpt_companion import ChatGPTTimerState
from runtime import BridgeRuntime


class TimerRuntimeStartTests(unittest.TestCase):
    def _runtime(self):
        runtime = BridgeRuntime.__new__(
            BridgeRuntime
        )
        runtime.chatgpt_timer = (
            ChatGPTTimerState()
        )
        return runtime
    def test_first_call_starts_and_claims(self):
        runtime = self._runtime()

        result = runtime.ensure_chatgpt_turn(
            reason="/v1/status"
        )
        snapshot = runtime.chatgpt_timer.snapshot()

        self.assertTrue(result["started"])
        self.assertEqual(
            snapshot["state"],
            "RUNNING",
        )
        self.assertTrue(
            snapshot["claimed_by_codebridge"]
        )
        self.assertEqual(
            snapshot["claim_reason"],
            "/v1/status",
        )
    def test_repeated_call_does_not_restart(self):
        runtime = self._runtime()
        first = runtime.ensure_chatgpt_turn()
        first_id = first["timer"]["request_id"]

        time.sleep(0.01)
        second = runtime.ensure_chatgpt_turn()
        second_id = second["timer"]["request_id"]

        self.assertFalse(second["started"])
        self.assertEqual(first_id, second_id)
        self.assertGreater(
            second["timer"]["elapsed_seconds"],
            0,
        )

    def test_finish_then_next_call_starts_new_turn(self):
        runtime = self._runtime()
        first = runtime.ensure_chatgpt_turn()
        first_id = first["timer"]["request_id"]

        finished = runtime.chatgpt_timer.finish(
            None
        )
        self.assertEqual(
            finished["timer"]["state"],
            "FINISHED",
        )

        second = runtime.ensure_chatgpt_turn()
        second_id = second["timer"]["request_id"]

        self.assertTrue(second["started"])
        self.assertNotEqual(first_id, second_id)
        self.assertTrue(
            second["timer"]["claimed_by_codebridge"]
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
