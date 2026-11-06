import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app_rewrite"

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from chatgpt_companion import ChatGPTTimerState
from claude_desktop_watcher import ClaudeDesktopWatcher
from config_store import ConfigStore, normalize_turn_timer_mode
from runtime import BridgeRuntime


class FakeConfig:
    def __init__(self):
        self.saved = []

    def save_turn_timer_mode(self, mode):
        self.saved.append(mode)
        return mode


class FakeTerminals:
    def __init__(self):
        self.config = FakeConfig()


class FakeWatcher:
    def __init__(self):
        self.running = False

    def start(self):
        self.running = True
        return True

    def stop(self):
        self.running = False
        return True

    def status(self):
        return {"running": self.running}


def make_runtime(mode, started=False):
    runtime = BridgeRuntime.__new__(BridgeRuntime)
    runtime.finished_calls = []
    runtime.chatgpt_timer = ChatGPTTimerState(
        on_finished=lambda rid, timer: runtime.finished_calls.append(rid)
    )
    runtime.terminals = FakeTerminals()
    runtime.turn_timer_mode = mode
    runtime.claude_watcher = FakeWatcher()
    runtime._started = started
    return runtime


class ConfigTurnTimerModeTests(unittest.TestCase):
    def test_default_and_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ConfigStore(Path(tmp) / "config.json")
            self.assertEqual(store.load_turn_timer_mode(), "CHATGPT")
            store.save_turn_timer_mode("claude")
            self.assertEqual(store.load_turn_timer_mode(), "CLAUDE")
            store.save_turn_timer_mode("DISABLED")
            self.assertEqual(store.load_turn_timer_mode(), "DISABLED")

    def test_invalid_mode_rejected(self):
        with self.assertRaises(ValueError):
            normalize_turn_timer_mode("gemini")

    def test_corrupt_value_falls_back_to_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text('{"turn_timer_mode": "xyz"}', encoding="utf-8")
            self.assertEqual(
                ConfigStore(path).load_turn_timer_mode(),
                "CHATGPT",
            )


class RuntimeTurnTimerModeTests(unittest.TestCase):
    def test_disabled_never_starts_a_turn(self):
        runtime = make_runtime("DISABLED")
        result = runtime.ensure_chatgpt_turn(track_activity=True)
        self.assertFalse(result["started"])
        self.assertTrue(result["disabled"])
        self.assertEqual(
            runtime.chatgpt_timer.turn_control()["stage"],
            "INACTIVE",
        )

    def test_switch_to_disabled_resets_running_turn(self):
        runtime = make_runtime("CHATGPT")
        runtime.ensure_chatgpt_turn()
        runtime.set_turn_timer_mode("DISABLED")
        self.assertEqual(runtime.chatgpt_timer.snapshot()["state"], "IDLE")
        self.assertEqual(runtime.terminals.config.saved, ["DISABLED"])

    def test_chatgpt_mode_ignores_idle_gap(self):
        runtime = make_runtime("CHATGPT")
        first = runtime.ensure_chatgpt_turn(track_activity=True, now=0.0)
        runtime.end_chatgpt_activity(now=1.0)
        second = runtime.ensure_chatgpt_turn(now=5000.0)
        self.assertFalse(second["started"])
        self.assertEqual(
            first["timer"]["request_id"],
            second["timer"]["request_id"],
        )

    def test_claude_watcher_finish_closes_claimed_turn(self):
        runtime = make_runtime("CLAUDE")
        first = runtime.ensure_chatgpt_turn()
        self.assertTrue(runtime._on_claude_response_finished())
        self.assertEqual(runtime.chatgpt_timer.snapshot()["state"], "FINISHED")
        self.assertEqual(
            runtime.finished_calls,
            [first["timer"]["request_id"]],
        )
        second = runtime.ensure_chatgpt_turn()
        self.assertTrue(second["started"])

    def test_claude_watcher_finish_ignored_in_chatgpt_mode(self):
        runtime = make_runtime("CHATGPT")
        runtime.ensure_chatgpt_turn()
        self.assertFalse(runtime._on_claude_response_finished())
        self.assertEqual(runtime.chatgpt_timer.snapshot()["state"], "RUNNING")

    def test_watcher_follows_mode_when_started(self):
        runtime = make_runtime("CHATGPT", started=True)
        runtime.set_turn_timer_mode("CLAUDE")
        self.assertTrue(runtime.claude_watcher.running)
        runtime.set_turn_timer_mode("CHATGPT")
        self.assertFalse(runtime.claude_watcher.running)

    def test_watcher_not_started_before_runtime_start(self):
        runtime = make_runtime("CHATGPT", started=False)
        runtime.set_turn_timer_mode("CLAUDE")
        self.assertFalse(runtime.claude_watcher.running)


class ClaudeDesktopWatcherTests(unittest.TestCase):
    def test_running_then_idle_reports_finish(self):
        calls = []
        watcher = ClaudeDesktopWatcher(lambda: calls.append(1))
        watcher.consume(
            ["IDLE\n", "RUNNING\n", "IDLE\n", "RUNNING\n", "NO_APP\n"]
        )
        self.assertEqual(len(calls), 2)
        self.assertEqual(watcher.status()["finished_responses"], 2)

    def test_no_finish_without_prior_running(self):
        calls = []
        watcher = ClaudeDesktopWatcher(lambda: calls.append(1))
        watcher.consume(["IDLE", "NO_APP", "", "IDLE"])
        self.assertEqual(calls, [])

    def test_callback_error_does_not_stop_watcher(self):
        def boom():
            raise RuntimeError("x")

        watcher = ClaudeDesktopWatcher(boom)
        watcher.consume(["RUNNING", "IDLE", "RUNNING", "IDLE"])
        self.assertEqual(watcher.status()["finished_responses"], 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
