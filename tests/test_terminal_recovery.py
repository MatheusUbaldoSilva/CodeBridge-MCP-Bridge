import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app_rewrite"

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from terminal_manager import TerminalManager
from runtime import BridgeRuntime


class ImmediateThread:
    def __init__(self, target, args=(), **kwargs):
        self.target = target
        self.args = args

    def start(self):
        self.target(*self.args)


class FakeSession:
    def __init__(self):
        self.is_executing = True
        self.is_running = True
        self.cancel_calls = 0

    def cancel_current(self):
        self.cancel_calls += 1
        self.is_executing = False
        return True


class TerminalCancelRecoveryTests(unittest.TestCase):
    def _manager(self, active):
        manager = TerminalManager.__new__(
            TerminalManager
        )
        manager._lock = threading.RLock()
        manager._recovery_lock = threading.Lock()
        manager._recovering_targets = set()
        manager.active_target = active
        manager._prepared_target = active
        manager.windows = FakeSession()
        manager.cmd = FakeSession()
        manager.ssh = FakeSession()
        manager.recycle = Mock(return_value=True)
        return manager

    def test_cancel_recycles_each_terminal(self):
        cases = (
            ("POWERSHELL5.1", "windows"),
            ("CMD", "cmd"),
            ("SSH", "ssh"),
        )

        for target, attr in cases:
            with self.subTest(target=target):
                manager = self._manager(target)
                session = getattr(manager, attr)

                with patch(
                    "terminal_manager.threading.Thread",
                    ImmediateThread,
                ):
                    result = manager.cancel_active()

                self.assertTrue(result)
                self.assertEqual(
                    session.cancel_calls,
                    1,
                )
                manager.recycle.assert_called_once_with(
                    target,
                    reason=(
                        "cancelamento confirmado/forcado"
                    ),
                )


class FakeTerminals:
    def __init__(self):
        self.recycled = []

    def recycle(self, target, reason):
        self.recycled.append((target, reason))
        return True

    def recover_orphaned(self, target, reason):
        self.recycled.append((target, reason))
        return True

    def ensure_local_online(self):
        return False

    def status(self):
        return {
            "powershell": {
                "online": True,
                "executing": False,
            },
            "cmd": {
                "online": True,
                "executing": False,
            },
            "ssh": {
                "online": True,
                "executing": False,
            },
            "active_target": None,
            "prepared_target": None,
        }


class FakeStore:
    def __init__(self):
        self.calls = 0

    def recover_orphaned(self, runtime_instance):
        self.calls += 1
        return 1


class FakeLedger:
    def list_by_state(self, *states):
        return []


class RuntimeOrphanRecoveryTests(unittest.TestCase):
    def _runtime(self, active_job_id=None):
        runtime = BridgeRuntime.__new__(
            BridgeRuntime
        )
        runtime.instance_id = "runtime-test"
        runtime.terminals = FakeTerminals()
        runtime.engine = type(
            "Engine",
            (),
            {"active_job_id": active_job_id},
        )()
        runtime._phase5b_lock = threading.RLock()
        runtime._phase5b_active_execution_id = None
        runtime._external_prepared_request_id = None
        runtime._external_prepared_target = None
        runtime._external_prepared_command = None
        runtime._external_workers_lock = (
            threading.RLock()
        )
        runtime._external_workers = {}
        runtime.external_executions = FakeStore()
        runtime.external_prepares = FakeStore()
        runtime.execution_ledger = FakeLedger()
        return runtime

    def test_orphaned_cmd_is_recycled(self):
        runtime = self._runtime()
        stale = {
            "powershell": {
                "online": True,
                "executing": False,
            },
            "cmd": {
                "online": True,
                "executing": True,
            },
            "ssh": {
                "online": True,
                "executing": False,
            },
            "active_target": "CMD",
            "prepared_target": "CMD",
        }

        result = (
            runtime._recover_orphaned_terminal_state(
                stale
            )
        )

        self.assertIn(
            ("CMD", "estado sem owner ativo"),
            runtime.terminals.recycled,
        )
        self.assertEqual(
            runtime.external_executions.calls,
            1,
        )
        self.assertEqual(
            runtime.external_prepares.calls,
            1,
        )
        self.assertFalse(
            result["cmd"]["executing"]
        )

    def test_live_v2_worker_is_owner_before_active_id(self):
        runtime = self._runtime()
        runtime._phase5b_workers = {
            "exec-new": type(
                "Worker",
                (),
                {"is_alive": lambda self: True},
            )()
        }

        self.assertTrue(
            runtime._runtime_has_terminal_owner()
        )

    def test_legitimate_owner_is_not_recycled(self):
        runtime = self._runtime(
            active_job_id="job-1"
        )
        active = {
            "powershell": {
                "online": True,
                "executing": False,
            },
            "cmd": {
                "online": True,
                "executing": True,
            },
            "ssh": {
                "online": True,
                "executing": False,
            },
            "active_target": "CMD",
            "prepared_target": "CMD",
        }

        result = (
            runtime._recover_orphaned_terminal_state(
                active
            )
        )

        self.assertEqual(
            runtime.terminals.recycled,
            [],
        )
        self.assertTrue(
            result["cmd"]["executing"]
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
