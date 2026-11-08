import json
import sys
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app_rewrite"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from api_server import BridgeAPI  # noqa: E402
from chatgpt_companion import ChatGPTTimerState  # noqa: E402
from rag_query_counter import RagQueryCounter  # noqa: E402
from runtime import BridgeRuntime  # noqa: E402


class CounterTest(unittest.TestCase):
    def test_session_and_cycle_counts(self):
        counter = RagQueryCounter(clock=lambda: 100.0)
        counter.record("MCP", "c1")
        counter.record("MCP", "c1")
        counter.record("TELA", "c1")
        snap = counter.snapshot("c1")
        self.assertEqual(snap["cycle_total"], 3)
        self.assertEqual(snap["cycle_by_source"], {"MCP": 2, "TELA": 1, "IA_LOCAL": 0})
        self.assertEqual(snap["session_total"], 3)

    def test_new_cycle_starts_from_zero_and_session_keeps_going(self):
        counter = RagQueryCounter()
        counter.record("MCP", "c1")
        counter.record("MCP", "c1")
        self.assertEqual(counter.snapshot("c2")["cycle_total"], 0)
        counter.record("MCP", "c2")
        self.assertEqual(counter.snapshot("c2")["cycle_total"], 1)
        self.assertEqual(counter.snapshot("c1")["cycle_total"], 0)
        self.assertEqual(counter.snapshot()["session_total"], 3)

    def test_query_outside_cycle_counts_only_in_session(self):
        counter = RagQueryCounter()
        counter.record("MCP", None)
        counter.record("qualquer", "")
        snap = counter.snapshot(None)
        self.assertEqual(snap["session_total"], 2)
        self.assertEqual(snap["session_by_source"]["MCP"], 2)
        self.assertEqual(snap["cycle_total"], 0)


def make_runtime(mode="CLAUDE"):
    runtime = BridgeRuntime.__new__(BridgeRuntime)
    runtime.turn_timer_mode = mode
    runtime.chatgpt_timer = ChatGPTTimerState()
    runtime.rag_queries = RagQueryCounter()
    return runtime


class RuntimeCountTest(unittest.TestCase):
    def test_running_cycle_receives_queries(self):
        runtime = make_runtime()
        runtime.chatgpt_timer.start("turn-1")
        runtime.record_rag_query("MCP")
        runtime.record_rag_query("TELA")
        counts = runtime.rag_query_counts()
        self.assertEqual(counts["cycle_total"], 2)
        runtime.chatgpt_timer.finish("turn-1", notify=False)
        self.assertEqual(runtime.rag_query_counts()["cycle_total"], 2)
        runtime.record_rag_query("MCP")
        self.assertEqual(runtime.rag_query_counts()["cycle_total"], 2)
        runtime.chatgpt_timer.start("turn-2")
        self.assertEqual(runtime.rag_query_counts()["cycle_total"], 0)
        self.assertEqual(runtime.rag_query_counts()["session_total"], 3)

    def test_disabled_timer_counts_whole_session(self):
        runtime = make_runtime("DISABLED")
        runtime.chatgpt_timer.start("turn-x")
        for _ in range(4):
            runtime.record_rag_query("MCP")
        counts = runtime.rag_query_counts()
        self.assertEqual(counts["session_total"], 4)
        self.assertEqual(counts["cycle_total"], 0)
        self.assertIsNone(counts["cycle_key"])

    def test_counter_created_lazily(self):
        runtime = BridgeRuntime.__new__(BridgeRuntime)
        runtime.turn_timer_mode = "DISABLED"
        runtime.chatgpt_timer = ChatGPTTimerState()
        runtime.record_rag_query("MCP")
        self.assertEqual(runtime.rag_query_counts()["session_total"], 1)


class FakeRuntime:
    def __init__(self):
        self.calls = []

    def record_rag_query(self, source):
        self.calls.append(source)
        return {"session_total": len(self.calls)}

    def ensure_chatgpt_turn(self, **kwargs):
        raise AssertionError("contar consulta nao pode abrir nem prolongar turno")


class ApiRouteTest(unittest.TestCase):
    def test_query_event_route_does_not_touch_turn(self):
        runtime = FakeRuntime()
        api = BridgeAPI(runtime, port=0, token="tok")
        api.start()
        try:
            request = urllib.request.Request(
                f"http://127.0.0.1:{api.port}/v1/rag/query-event",
                data=json.dumps({"source": "MCP"}).encode("utf-8"),
                headers={"Authorization": "Bearer tok", "Content-Type": "application/json"},
                method="POST")
            with urllib.request.urlopen(request, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
        finally:
            api.stop()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["rag_queries"], {"session_total": 1})
        self.assertEqual(runtime.calls, ["MCP"])


if __name__ == "__main__":
    unittest.main()