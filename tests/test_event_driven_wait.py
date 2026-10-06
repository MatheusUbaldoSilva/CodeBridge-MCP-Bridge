import sys
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app_rewrite"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from runtime import BridgeRuntime


def empty_result():
    return {
        "execution_id": "e1",
        "target": "POWERSHELL5.1",
        "state": "RUNNING",
        "text": "",
        "next_cursor": 0,
        "has_more": False,
        "complete": False,
        "eof": False,
    }


class EventDrivenWaitTests(unittest.TestCase):
    def make_bridge(self, reader):
        bridge = BridgeRuntime.__new__(BridgeRuntime)
        bridge._execution_signal_condition = threading.Condition(
            threading.RLock()
        )
        bridge._execution_signal_generation = 0
        bridge.phase5f_execution_output = reader
        return bridge

    def test_timeout_waits_without_polling_loop(self):
        calls = []

        def reader(*args, **kwargs):
            calls.append(time.monotonic())
            return empty_result()

        bridge = self.make_bridge(reader)
        started = time.monotonic()
        result = bridge.phase5f_wait_execution_output(
            "e1",
            timeout_ms=60,
        )
        elapsed = time.monotonic() - started

        self.assertTrue(result["timed_out"])
        self.assertEqual(result["wait_mode"], "EVENT")
        self.assertGreaterEqual(elapsed, 0.04)
        self.assertLess(elapsed, 0.40)
        # Initial read plus one boundary read, never 100 ms polling.
        self.assertLessEqual(len(calls), 2)

    def test_output_signal_wakes_wait_early(self):
        state = {"text": ""}
        calls = []

        def reader(*args, **kwargs):
            calls.append(time.monotonic())
            result = empty_result()
            result["text"] = state["text"]
            result["next_cursor"] = len(state["text"])
            return result

        bridge = self.make_bridge(reader)
        box = {}

        def wait():
            box["result"] = (
                bridge.phase5f_wait_execution_output(
                    "e1",
                    timeout_ms=3000,
                )
            )

        thread = threading.Thread(target=wait)
        started = time.monotonic()
        thread.start()
        time.sleep(0.06)
        state["text"] = "NEW"
        bridge._signal_execution_change()
        thread.join(timeout=1.0)

        self.assertFalse(thread.is_alive())
        self.assertEqual(box["result"]["text"], "NEW")
        self.assertFalse(box["result"]["timed_out"])
        self.assertLess(time.monotonic() - started, 0.8)
        self.assertLessEqual(len(calls), 2)

    def test_terminal_signal_wakes_wait(self):
        state = {"complete": False}

        def reader(*args, **kwargs):
            result = empty_result()
            result["complete"] = state["complete"]
            if state["complete"]:
                result["state"] = "FINISHED"
                result["eof"] = True
            return result

        bridge = self.make_bridge(reader)
        box = {}

        thread = threading.Thread(
            target=lambda: box.setdefault(
                "result",
                bridge.phase5f_wait_execution_output(
                    "e1",
                    timeout_ms=3000,
                ),
            )
        )
        thread.start()
        time.sleep(0.05)
        state["complete"] = True
        bridge._signal_execution_change()
        thread.join(timeout=1.0)

        self.assertFalse(thread.is_alive())
        self.assertTrue(box["result"]["complete"])
        self.assertEqual(
            box["result"]["state"],
            "FINISHED",
        )
        self.assertFalse(box["result"]["timed_out"])

    def test_signal_between_read_and_sleep_is_not_lost(self):
        calls = {"count": 0}
        bridge_box = {}

        def reader(*args, **kwargs):
            calls["count"] += 1
            result = empty_result()
            if calls["count"] == 1:
                bridge_box["bridge"]._signal_execution_change()
            else:
                result["text"] = "RACE_OK"
                result["next_cursor"] = 7
            return result

        bridge = self.make_bridge(reader)
        bridge_box["bridge"] = bridge
        started = time.monotonic()
        result = bridge.phase5f_wait_execution_output(
            "e1",
            timeout_ms=2000,
        )

        self.assertEqual(result["text"], "RACE_OK")
        self.assertFalse(result["timed_out"])
        self.assertEqual(calls["count"], 2)
        self.assertLess(time.monotonic() - started, 0.3)


if __name__ == "__main__":
    unittest.main()
