"""Secure tunnel startup must pass the real profile file, not a search-only name."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app_rewrite"))
from secure_tunnel_manager import SecureTunnelManager


class TunnelProfilePathTests(unittest.TestCase):
    def test_launch_uses_explicit_config_path(self):
        mgr = object.__new__(SecureTunnelManager)
        mgr.client = Path(r"C:\Tools\tunnel-client.exe")
        mgr.profile = Path(r"C:\Users\Test User\AppData\Roaming\tunnel-client\codebridge-local.yaml")
        self.assertEqual(
            mgr._run_command(),
            [str(mgr.client), "run", "--config", str(mgr.profile)],
        )

    def test_file_path_does_not_depend_on_default_search_dir(self):
        mgr = object.__new__(SecureTunnelManager)
        mgr.client = Path(r"C:\CodeBridge\tunnel-client.exe")
        mgr.profile = Path(r"C:\Users\Matheus\AppData\Roaming\tunnel-client\custom.yaml")
        command = mgr._run_command()
        self.assertEqual(command[2], "--config")
        self.assertEqual(command[3], str(mgr.profile))
        self.assertNotIn("--profile", command)


if __name__ == "__main__":
    unittest.main(verbosity=2)
