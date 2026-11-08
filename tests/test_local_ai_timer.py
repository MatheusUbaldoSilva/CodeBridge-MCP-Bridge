"""IA Local conta no cronometro de turno (ChatGPT ou Claude); Desabilitado nao conta."""
import os
import sys
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app_rewrite"
for path in (str(APP_DIR), str(ROOT), str(ROOT / "tests")):
    if path not in sys.path:
        sys.path.insert(0, path)

from chatgpt_companion import ChatGPTTimerState  # noqa: E402
from runtime import BridgeRuntime  # noqa: E402


def make_runtime(mode):
    runtime = BridgeRuntime.__new__(BridgeRuntime)
    runtime.turn_timer_mode = mode
    runtime.chatgpt_timer = ChatGPTTimerState()
    return runtime


class RuntimeLocalAiTurnTest(unittest.TestCase):
    def test_counts_in_chatgpt_and_claude_modes(self):
        for mode in ("CHATGPT", "CLAUDE"):
            runtime = make_runtime(mode)
            request = runtime.begin_local_ai_turn()
            self.assertTrue(request, mode)
            timer = runtime.chatgpt_timer.snapshot()
            self.assertEqual(timer["state"], "RUNNING", mode)
            self.assertEqual(timer["request_id"], request)
            self.assertTrue(runtime.end_local_ai_turn(request))
            self.assertEqual(runtime.chatgpt_timer.snapshot()["state"], "FINISHED", mode)

    def test_disabled_does_not_count(self):
        runtime = make_runtime("DISABLED")
        self.assertIsNone(runtime.begin_local_ai_turn())
        self.assertEqual(runtime.chatgpt_timer.snapshot()["state"], "IDLE")
        self.assertFalse(runtime.end_local_ai_turn(None))
        self.assertEqual(runtime.chatgpt_timer.snapshot()["state"], "IDLE")

    def test_joins_turn_already_running(self):
        runtime = make_runtime("CLAUDE")
        runtime.ensure_chatgpt_turn(reason="codebridge_call")
        claude_turn = runtime.chatgpt_timer.snapshot()["request_id"]
        self.assertEqual(runtime.begin_local_ai_turn(), "")
        self.assertFalse(runtime.end_local_ai_turn(""))
        timer = runtime.chatgpt_timer.snapshot()
        self.assertEqual(timer["state"], "RUNNING")  # o turno do Claude continua
        self.assertEqual(timer["request_id"], claude_turn)

    def test_stop_cancels_the_turn(self):
        runtime = make_runtime("CHATGPT")
        request = runtime.begin_local_ai_turn()
        runtime.end_local_ai_turn(request, cancelled=True)
        self.assertEqual(runtime.chatgpt_timer.snapshot()["state"], "CANCELLED")


class PanelTurnTimerTest(unittest.TestCase):
    def test_each_request_opens_and_closes_a_turn(self):
        from PySide6.QtWidgets import QApplication
        import local_ai_panel as panel_mod
        from test_local_ai_panel import FakeServer, Runner, ScriptedClient, pump

        QApplication.instance() or QApplication([])
        runtime = make_runtime("CLAUDE")
        seen = []
        original = runtime.begin_local_ai_turn

        def begin():
            request = original()
            seen.append(runtime.chatgpt_timer.snapshot()["state"])
            return request

        runtime.begin_local_ai_turn = begin
        client = ScriptedClient([{"content": "Oi."}])
        panel = panel_mod.LocalAiPanel(
            runtime, project_id=lambda: "codebridge", project_root=lambda: None,
            search_fn=lambda q, p, k: {"results": []}, server=FakeServer(),
            runner=Runner(), client_factory=lambda: client)
        self.addCleanup(panel.shutdown)
        panel.input.setPlainText("oi")
        panel.send()
        self.assertTrue(pump(panel, lambda: not panel.agent.running))
        deadline = time.time() + 2
        while runtime.chatgpt_timer.snapshot()["state"] == "RUNNING" and time.time() < deadline:
            time.sleep(0.02)
        self.assertEqual(seen, ["RUNNING"])
        self.assertEqual(runtime.chatgpt_timer.snapshot()["state"], "FINISHED")

    def test_disabled_timer_is_left_alone(self):
        from PySide6.QtWidgets import QApplication
        import local_ai_panel as panel_mod
        from test_local_ai_panel import FakeServer, Runner, ScriptedClient, pump

        QApplication.instance() or QApplication([])
        runtime = make_runtime("DISABLED")
        panel = panel_mod.LocalAiPanel(
            runtime, project_id=lambda: "codebridge", project_root=lambda: None,
            search_fn=lambda q, p, k: {"results": []}, server=FakeServer(),
            runner=Runner(), client_factory=lambda: ScriptedClient([{"content": "Oi."}]))
        self.addCleanup(panel.shutdown)
        panel.input.setPlainText("oi")
        panel.send()
        self.assertTrue(pump(panel, lambda: not panel.agent.running))
        self.assertEqual(runtime.chatgpt_timer.snapshot()["state"], "IDLE")


if __name__ == "__main__":
    unittest.main()
