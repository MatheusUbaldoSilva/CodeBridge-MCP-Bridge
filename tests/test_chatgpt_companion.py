import json
import sys
import time
import unittest
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app_rewrite"

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from chatgpt_companion import (
    COMPANION_HEADER,
    COMPANION_HEADER_VALUE,
    PREPARE_WRAP_UP_SECONDS,
    WRAP_UP_SECONDS,
    ChatGPTCompanionServer,
    ChatGPTTimerState,
)


class ChatGPTTimerStateTests(unittest.TestCase):
    def test_start_finish_freezes_elapsed(self):
        timer = ChatGPTTimerState()
        timer.start("req-1")
        time.sleep(0.03)
        running = timer.snapshot()
        self.assertEqual(running["state"], "RUNNING")
        self.assertGreater(running["elapsed_seconds"], 0)

        timer.finish("req-1")
        finished = timer.snapshot()
        time.sleep(0.03)
        after = timer.snapshot()

        self.assertEqual(finished["state"], "FINISHED")
        self.assertAlmostEqual(
            finished["elapsed_seconds"],
            after["elapsed_seconds"],
            places=3,
        )

    def test_stale_finish_does_not_stop_new_request(self):
        timer = ChatGPTTimerState()
        timer.start("old")
        timer.start("new")
        result = timer.finish("old")

        self.assertFalse(result["applied"])
        self.assertEqual(
            timer.snapshot()["request_id"],
            "new",
        )
        self.assertEqual(
            timer.snapshot()["state"],
            "RUNNING",
        )

    def test_cancel(self):
        timer = ChatGPTTimerState()
        timer.start("req-cancel")
        timer.cancel("req-cancel")
        self.assertEqual(
            timer.snapshot()["state"],
            "CANCELLED",
        )

    @staticmethod
    def _force_elapsed(timer, seconds):
        with timer._lock:
            timer._started_monotonic = (
                time.monotonic()
                - float(seconds)
            )

    def test_turn_control_normal(self):
        timer = ChatGPTTimerState()
        timer.start("normal")
        self._force_elapsed(
            timer,
            PREPARE_WRAP_UP_SECONDS - 1,
        )
        control = timer.turn_control()
        self.assertEqual(
            control["stage"],
            "NORMAL",
        )
        self.assertEqual(
            control["action"],
            "CONTINUE",
        )
        self.assertFalse(
            control["request_wrap_up"]
        )

    def test_turn_control_prepare_wrap_up(self):
        timer = ChatGPTTimerState()
        timer.start("prepare")
        self._force_elapsed(
            timer,
            PREPARE_WRAP_UP_SECONDS + 0.1,
        )
        control = timer.turn_control()
        self.assertEqual(
            control["stage"],
            "PREPARE_WRAP_UP",
        )
        self.assertEqual(
            control["action"],
            "PREPARE_CHECKPOINT",
        )
        self.assertFalse(
            control["request_wrap_up"]
        )

    def test_turn_control_wrap_up_now(self):
        timer = ChatGPTTimerState()
        timer.start("wrap")
        self._force_elapsed(
            timer,
            WRAP_UP_SECONDS + 0.1,
        )
        control = timer.turn_control()
        self.assertEqual(
            control["stage"],
            "WRAP_UP_NOW",
        )
        self.assertEqual(
            control["action"],
            "FINISH_RESPONSE_NORMALLY",
        )
        self.assertTrue(
            control["request_wrap_up"]
        )
        self.assertIn(
            "continuar",
            control["directive"],
        )
        self.assertIn(
            "Do not cancel",
            control["directive"],
        )

    def test_turn_control_inactive_after_finish(self):
        timer = ChatGPTTimerState()
        timer.start("done")
        timer.finish("done")
        control = timer.turn_control()
        self.assertEqual(
            control["stage"],
            "INACTIVE",
        )
        self.assertEqual(
            control["action"],
            "NONE",
        )

    def test_manual_wrap_up_is_immediate(self):
        timer = ChatGPTTimerState()
        timer.start("manual")
        result = timer.request_manual_wrap_up()
        control = result["turn_control"]

        self.assertTrue(result["applied"])
        self.assertEqual(
            control["stage"],
            "WRAP_UP_NOW",
        )
        self.assertEqual(
            control["action"],
            "FINISH_RESPONSE_NORMALLY",
        )
        self.assertTrue(
            control["request_wrap_up"]
        )
        self.assertTrue(
            control["manual_request"]
        )
        self.assertEqual(
            control["reason"],
            "manual_stop_button",
        )

    def test_new_request_preserves_manual_wrap_up(self):
        timer = ChatGPTTimerState()
        timer.start("first")
        timer.request_manual_wrap_up()
        timer.start("other-message")

        control = timer.turn_control()
        self.assertEqual(
            control["stage"],
            "WRAP_UP_NOW",
        )
        self.assertTrue(
            control["manual_request"]
        )
        self.assertTrue(
            control["request_wrap_up"]
        )

    def test_continue_request_clears_manual_wrap_up(self):
        timer = ChatGPTTimerState()
        timer.start("first")
        timer.request_manual_wrap_up()
        timer.start(
            "continue",
            resume_manual=True,
        )

        control = timer.turn_control()
        self.assertEqual(
            control["stage"],
            "NORMAL",
        )
        self.assertFalse(
            control["manual_request"]
        )
        self.assertFalse(
            control["request_wrap_up"]
        )


class ChatGPTCompanionServerTests(unittest.TestCase):
    def setUp(self):
        self.timer = ChatGPTTimerState()
        self.server = ChatGPTCompanionServer(
            self.timer,
            host="127.0.0.1",
            port=0,
        )
        self.server.start()
        self.base = (
            "http://127.0.0.1:"
            + str(self.server.port)
        )

    def tearDown(self):
        self.server.stop()

    def _post(self, action, request_id):
        payload = json.dumps(
            {"request_id": request_id}
        ).encode("utf-8")
        request = Request(
            self.base
            + "/v1/chatgpt/timer/"
            + action,
            data=payload,
            method="POST",
            headers={
                "Content-Type": "application/json",
                COMPANION_HEADER:
                    COMPANION_HEADER_VALUE,
            },
        )
        with urlopen(
            request,
            timeout=2,
        ) as response:
            return json.loads(
                response.read().decode("utf-8")
            )

    def test_http_start_finish(self):
        started = self._post(
            "start",
            "http-1",
        )
        self.assertTrue(started["ok"])
        self.assertEqual(
            started["timer"]["state"],
            "RUNNING",
        )

        finished = self._post(
            "finish",
            "http-1",
        )
        self.assertTrue(finished["ok"])
        self.assertEqual(
            finished["timer"]["state"],
            "FINISHED",
        )


if __name__ == "__main__":
    unittest.main()
