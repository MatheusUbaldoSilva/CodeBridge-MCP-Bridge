import sys
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app_rewrite"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import runtime as runtime_module
from runtime import BridgeRuntime


class CounterProbe:
    def __init__(self, name):
        self.name = name
        self.calls = 0

    def status(self):
        self.calls += 1
        return {
            "name": self.name,
            "generation": self.calls,
        }


class SequenceTerminals:
    def __init__(self):
        self.calls = 0

    def status(self):
        self.calls += 1
        active = self.calls >= 2
        return {
            "powershell": {
                "online": True,
                "executing": active,
                "recovering": False,
            },
            "cmd": {
                "online": True,
                "executing": False,
                "recovering": False,
            },
            "ssh": {
                "configured": True,
                "online": True,
                "executing": False,
                "recovering": False,
                "last_error": None,
            },
            "active_target": (
                "POWERSHELL5.1" if active else None
            ),
            "prepared_target": None,
            "execution_generation": self.calls,
            "last_execution_target": (
                "POWERSHELL5.1" if active else None
            ),
        }


class StatusAvailabilityCacheTests(unittest.TestCase):
    def make_runtime(self):
        bridge = BridgeRuntime.__new__(BridgeRuntime)
        bridge._availability_cache_lock = threading.RLock()
        bridge._availability_cache = None
        bridge._availability_cache_at = 0.0
        bridge.author_mcp = CounterProbe("mcp")
        bridge.secure_tunnel = CounterProbe("tunnel")
        return bridge

    def test_availability_cache_expires_and_is_copy_safe(self):
        bridge = self.make_runtime()
        with patch.object(
            runtime_module.time,
            "monotonic",
            side_effect=[100.0, 100.1, 100.7],
        ):
            first = bridge._availability_status()
            first["author_mcp"]["generation"] = 999
            second = bridge._availability_status()
            third = bridge._availability_status()

        self.assertEqual(
            second["author_mcp"]["generation"],
            1,
        )
        self.assertEqual(
            third["author_mcp"]["generation"],
            2,
        )
        self.assertEqual(bridge.author_mcp.calls, 2)
        self.assertEqual(bridge.secure_tunnel.calls, 2)

    def test_explicit_invalidation_forces_fresh_probe(self):
        bridge = self.make_runtime()
        with patch.object(
            runtime_module.time,
            "monotonic",
            side_effect=[200.0, 200.1],
        ):
            bridge._availability_status()
            bridge._invalidate_availability_cache()
            fresh = bridge._availability_status()
        self.assertEqual(
            fresh["author_mcp"]["generation"],
            2,
        )
        self.assertEqual(bridge.author_mcp.calls, 2)

    def test_snapshot_never_caches_execution_state(self):
        bridge = self.make_runtime()
        bridge.terminals = SequenceTerminals()
        bridge._recover_orphaned_terminal_state = (
            lambda value: value
        )
        bridge.store = SimpleNamespace(
            counts=lambda: {"TOTAL": 0}
        )
        bridge.api = SimpleNamespace(
            running=True,
            host="127.0.0.1",
            port=1234,
        )
        bridge.auto_execute = True
        bridge.completion_sound = SimpleNamespace(
            enabled=True
        )
        bridge.engine = SimpleNamespace(
            running=True,
            active_job_id=None,
        )
        bridge._phase5b_lock = threading.RLock()
        bridge._phase5b_active_execution_id = None
        bridge.chatgpt_timer = SimpleNamespace(
            snapshot=lambda: {"state": "RUNNING"},
            turn_control=lambda: {"stage": "NORMAL"},
        )
        bridge.chatgpt_companion = SimpleNamespace(
            running=True,
            host="127.0.0.1",
            port=4321,
        )

        with patch.object(
            runtime_module.time,
            "monotonic",
            side_effect=[300.0, 300.1],
        ):
            first = bridge.snapshot()
            second = bridge.snapshot()

        self.assertFalse(
            first["terminals"]["powershell"]["executing"]
        )
        self.assertTrue(
            second["terminals"]["powershell"]["executing"]
        )
        self.assertIsNone(first["active_execution"])
        self.assertIsNone(second["active_execution"])
        self.assertEqual(bridge.author_mcp.calls, 1)
        self.assertEqual(bridge.secure_tunnel.calls, 1)
        self.assertEqual(bridge.terminals.calls, 2)


if __name__ == "__main__":
    unittest.main()