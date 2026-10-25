"""Regressions for CMD path resolution when Explorer has stale ComSpec."""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app_rewrite"))
from cmd_terminal_session import CmdTerminalSession


class CmdExecutableResolutionTests(unittest.TestCase):
    def test_invalid_comspec_uses_systemroot(self):
        env = {"ComSpec": r"C:\old-uninstalled-codebridge\cmd.exe", "SystemRoot": r"C:\Windows"}
        with patch.dict(os.environ, env, clear=True):
            obj = CmdTerminalSession()
        self.assertTrue(Path(obj._executable).is_file())
        self.assertEqual(Path(obj._executable).name.lower(), "cmd.exe")

    def test_empty_comspec_uses_fallback(self):
        with patch.dict(os.environ, {"ComSpec": "", "WINDIR": r"C:\Windows"}, clear=True):
            obj = CmdTerminalSession()
        self.assertTrue(Path(obj._executable).is_file())

    def test_relative_comspec_uses_system_cmd(self):
        with patch.dict(os.environ, {"ComSpec": "cmd.exe", "SystemRoot": r"C:\Windows"}, clear=True):
            obj = CmdTerminalSession()
        self.assertEqual(obj._executable.lower(), r"C:\Windows\System32\cmd.exe".lower())
        self.assertTrue(Path(obj._executable).is_file())

    def test_explicit_executable_is_not_replaced(self):
        expected = r"C:\Windows\System32\cmd.exe"
        obj = CmdTerminalSession(executable=expected)
        self.assertEqual(obj._executable.lower(), expected.lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
