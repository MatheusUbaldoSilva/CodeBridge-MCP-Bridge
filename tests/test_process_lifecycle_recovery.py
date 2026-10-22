# -*- coding: utf-8 -*-
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import psutil

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

    def test_reused_gui_pid_is_not_treated_as_live_ancestor(self):
        child=Mock()
        child.pid=30
        child.ppid.return_value=12
        child.create_time.return_value=100.0
        new_gui=Mock()
        new_gui.pid=12
        new_gui.ppid.return_value=0
        new_gui.create_time.return_value=200.0
        new_gui.cmdline.return_value=["pythonw.exe","C:/CodeBridge/app_rewrite/main.py"]
        new_gui.is_running.return_value=True
        with patch("author_mcp_manager.psutil.Process", return_value=new_gui):
            self.assertFalse(AuthorMCPManager._has_live_codebridge_ancestor(child))

    def test_older_gui_is_still_recognized(self):
        child=Mock()
        child.pid=30
        child.ppid.return_value=12
        child.create_time.return_value=200.0
        gui=Mock()
        gui.pid=12
        gui.ppid.return_value=0
        gui.create_time.return_value=100.0
        gui.cmdline.return_value=["pythonw.exe","C:/CodeBridge/app_rewrite/main.py"]
        gui.is_running.return_value=True
        with patch("author_mcp_manager.psutil.Process", return_value=gui):
            self.assertTrue(AuthorMCPManager._has_live_codebridge_ancestor(child))

    def test_ancestor_access_denied_is_not_evidence_of_orphan(self):
        child=Mock()
        child.pid=30
        child.ppid.return_value=12
        child.create_time.return_value=200.0
        with patch("author_mcp_manager.psutil.Process", side_effect=psutil.AccessDenied(12)):
            self.assertIsNone(AuthorMCPManager._has_live_codebridge_ancestor(child))

    def test_unknown_ownership_never_triggers_process_termination(self):
        manager=self.make_manager()
        manager._matching_stack_processes=Mock(return_value={
            "adapter":[{"pid":20,"live_codebridge_ancestor":False}],
            "mcp":[{"pid":30,"live_codebridge_ancestor":None}]
        })
        manager._terminate_pids=Mock()
        self.assertFalse(manager._recycle_inherited_stack({
            "adapter_online":True,"mcp_online":True
        }))
        manager._terminate_pids.assert_not_called()
        self.assertIn("nao verificavel",manager._last_error)

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
