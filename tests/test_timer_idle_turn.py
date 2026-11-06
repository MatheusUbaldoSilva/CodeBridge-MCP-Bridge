import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app_rewrite"

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from chatgpt_companion import ChatGPTTimerState
from runtime import (
    BridgeRuntime,
    CHATGPT_TURN_IDLE_GAP_SECONDS,
    CHATGPT_TURN_INFLIGHT_STALE_SECONDS,
)


class TimerIdleTurnTests(unittest.TestCase):
    def _runtime(self):
        self.finished_calls = []
        runtime = BridgeRuntime.__new__(BridgeRuntime)
        runtime.chatgpt_timer = ChatGPTTimerState(
            on_finished=lambda rid, timer: self.finished_calls.append(rid)
        )
        runtime.turn_timer_mode = "CLAUDE"
        return runtime

    def test_idle_gap_closes_turn_and_starts_new_one(self):
        runtime = self._runtime()
        first = runtime.ensure_chatgpt_turn(track_activity=True, now=0.0)
        runtime.end_chatgpt_activity(now=1.0)

        second = runtime.ensure_chatgpt_turn(
            track_activity=True,
            now=1.0 + CHATGPT_TURN_IDLE_GAP_SECONDS + 1,
        )

        self.assertTrue(second["started"])
        self.assertNotEqual(
            first["timer"]["request_id"],
            second["timer"]["request_id"],
        )
        self.assertEqual(
            second["idle_closed_request_id"],
            first["timer"]["request_id"],
        )
        self.assertLess(second["timer"]["elapsed_seconds"], 5)

    def test_short_gap_keeps_same_turn(self):
        runtime = self._runtime()
        first = runtime.ensure_chatgpt_turn(track_activity=True, now=0.0)
        runtime.end_chatgpt_activity(now=1.0)

        second = runtime.ensure_chatgpt_turn(
            now=1.0 + CHATGPT_TURN_IDLE_GAP_SECONDS - 1,
        )

        self.assertFalse(second["started"])
        self.assertEqual(
            first["timer"]["request_id"],
            second["timer"]["request_id"],
        )

    def test_request_in_flight_blocks_idle_close(self):
        runtime = self._runtime()
        first = runtime.ensure_chatgpt_turn(track_activity=True, now=0.0)

        second = runtime.ensure_chatgpt_turn(
            now=CHATGPT_TURN_IDLE_GAP_SECONDS * 2,
        )

        self.assertFalse(second["started"])
        self.assertEqual(
            first["timer"]["request_id"],
            second["timer"]["request_id"],
        )

    def test_stale_in_flight_does_not_lock_timer_forever(self):
        runtime = self._runtime()
        first = runtime.ensure_chatgpt_turn(track_activity=True, now=0.0)

        second = runtime.ensure_chatgpt_turn(
            now=CHATGPT_TURN_INFLIGHT_STALE_SECONDS + 1,
        )

        self.assertTrue(second["started"])
        self.assertNotEqual(
            first["timer"]["request_id"],
            second["timer"]["request_id"],
        )

    def test_idle_close_does_not_play_completion_sound(self):
        runtime = self._runtime()
        runtime.ensure_chatgpt_turn(track_activity=True, now=0.0)
        runtime.end_chatgpt_activity(now=1.0)
        runtime.ensure_chatgpt_turn(
            now=1.0 + CHATGPT_TURN_IDLE_GAP_SECONDS + 1,
        )

        self.assertEqual(self.finished_calls, [])

    def test_extension_finish_still_notifies(self):
        runtime = self._runtime()
        first = runtime.ensure_chatgpt_turn(now=0.0)
        runtime.chatgpt_timer.finish(first["timer"]["request_id"])

        self.assertEqual(
            self.finished_calls,
            [first["timer"]["request_id"]],
        )

    def test_wrap_up_clears_after_idle(self):
        runtime = self._runtime()
        runtime.ensure_chatgpt_turn(track_activity=True, now=0.0)
        runtime.chatgpt_timer.request_manual_wrap_up()
        self.assertEqual(
            runtime.chatgpt_timer.turn_control()["stage"],
            "WRAP_UP_NOW",
        )
        runtime.end_chatgpt_activity(now=1.0)

        runtime.ensure_chatgpt_turn(
            now=1.0 + CHATGPT_TURN_IDLE_GAP_SECONDS + 1,
        )

        self.assertEqual(
            runtime.chatgpt_timer.turn_control()["stage"],
            "NORMAL",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
