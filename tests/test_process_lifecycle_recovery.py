# -*- coding: utf-8 -*-
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app_rewrite"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from secure_tunnel_manager import SecureTunnelManager
from author_mcp_manager import AuthorMCPManager


class SecureTunnelLifecycleTests(unittest.TestCase):
    def make_manager(self):
        manager = SecureTunnelManager.__new__(
            SecureTunnelManager
        )
        manager._last_error = None
        manager._recycled_pid = None
        return manager

    def test_unknown_health_owner_is_never_killed(self):
        manager = self.make_manager()
        manager._health_online = Mock(return_value=True)
        manager._health_listener_pid = Mock(return_value=77)
        manager._existing_tunnel_info = Mock(
            return_value=None
        )
        manager._terminate_pid = Mock()

        self.assertFalse(
            manager._recycle_inherited_tunnel()
        )
        manager._terminate_pid.assert_not_called()
        self.assertIn(
            "nao reconhecido",
            manager._last_error,
        )

    def test_live_codebridge_owner_is_never_killed(self):
        manager = self.make_manager()
        manager._health_online = Mock(return_value=True)
        manager._health_listener_pid = Mock(return_value=88)
        manager._existing_tunnel_info = Mock(
            return_value={
                "is_codebridge_tunnel": True,
                "parent_is_live_codebridge": True,
            }
        )
        manager._terminate_pid = Mock()

        self.assertFalse(
            manager._recycle_inherited_tunnel()
        )
        manager._terminate_pid.assert_not_called()
        self.assertIn(
            "outra instancia ativa",
            manager._last_error,
        )

    def test_orphan_tunnel_is_recycled(self):
        manager = self.make_manager()
        manager._health_online = Mock(return_value=True)
        manager._health_listener_pid = Mock(return_value=99)
        manager._existing_tunnel_info = Mock(
            return_value={
                "is_codebridge_tunnel": True,
                "parent_is_live_codebridge": False,
            }
        )
        manager._terminate_pid = Mock()
        manager._wait_for = Mock(return_value=True)

        self.assertTrue(
            manager._recycle_inherited_tunnel()
        )
        manager._terminate_pid.assert_called_once_with(99)
        self.assertEqual(manager._recycled_pid, 99)


class AuthorMCPLifecycleTests(unittest.TestCase):
    def make_manager(self):
        manager = AuthorMCPManager.__new__(
            AuthorMCPManager
        )
        manager._last_error = None
        manager._recycled_pids = []
        return manager

    def test_live_stack_is_never_killed(self):
        manager = self.make_manager()
        manager._matching_stack_processes = Mock(
            return_value={
                "adapter": [{
                    "pid": 10,
                    "live_codebridge_ancestor": True,
                }],
                "mcp": [{
                    "pid": 11,
                    "live_codebridge_ancestor": True,
                }],
            }
        )
        manager._terminate_pids = Mock()

        current = {
            "adapter_online": True,
            "mcp_online": True,
        }
        self.assertFalse(
            manager._recycle_inherited_stack(current)
        )
        manager._terminate_pids.assert_not_called()
        self.assertIn(
            "outra instancia ativa",
            manager._last_error,
        )

    def test_orphan_stack_is_recycled(self):
        manager = self.make_manager()
        manager._matching_stack_processes = Mock(
            return_value={
                "adapter": [
                    {
                        "pid": 20,
                        "live_codebridge_ancestor": False,
                    },
                    {
                        "pid": 21,
                        "live_codebridge_ancestor": False,
                    },
                ],
                "mcp": [
                    {
                        "pid": 30,
                        "live_codebridge_ancestor": False,
                    },
                ],
            }
        )
        manager._terminate_pids = Mock()
        manager._wait_for = Mock(return_value=True)
        manager.probe = Mock()

        current = {
            "adapter_online": True,
            "mcp_online": True,
        }
        self.assertTrue(
            manager._recycle_inherited_stack(current)
        )
        manager._terminate_pids.assert_called_once()
        self.assertEqual(
            set(manager._terminate_pids.call_args.args[0]),
            {20, 21, 30},
        )
        self.assertEqual(
            manager._recycled_pids,
            [20, 21, 30],
        )

    def test_unknown_partial_stack_is_not_killed(self):
        manager = self.make_manager()
        manager._matching_stack_processes = Mock(
            return_value={
                "adapter": [],
                "mcp": [],
            }
        )
        manager._terminate_pids = Mock()

        current = {
            "adapter_online": False,
            "mcp_online": True,
        }
        self.assertFalse(
            manager._recycle_inherited_stack(current)
        )
        manager._terminate_pids.assert_not_called()
        self.assertIn(
            "nao reconhecido",
            manager._last_error,
        )


if __name__ == "__main__":
    unittest.main()
