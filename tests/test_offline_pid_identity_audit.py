"""PID identity audit must never authorize copying real RAG indexes."""
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rag.runtime.offline_pid_identity_audit import inspect_process_identities


class IdentityAuditTests(unittest.TestCase):
    def test_mcp_pid_identity_is_reported_without_cmdline(self):
        payload = [{"ProcessId": 987, "Name": "python.exe",
                    "ExecutablePath": "C:\\Python\\python.exe",
                    "CreationDate": "20261012190000.000000-180",
                    "CommandLine": "python mcp_server.py --secret hidden"}]
        report = inspect_process_identities(runner=lambda *a, **k:
            SimpleNamespace(stdout=json.dumps(payload)))
        self.assertEqual(report["state"], "BLOCKED")
        self.assertEqual(report["verified_pids"][0]["pid"], 987)
        self.assertNotIn("hidden", str(report))
        self.assertFalse(report["copy_authorized"])

    def test_no_suspects_never_authorizes(self):
        payload = [{"ProcessId": 1, "Name": "explorer.exe",
                    "ExecutablePath": "C:\\Windows\\explorer.exe",
                    "CreationDate": "20261012180000", "CommandLine": None}]
        report = inspect_process_identities(runner=lambda *a, **k:
            SimpleNamespace(stdout=json.dumps(payload)))
        self.assertEqual(report["state"], "NO_KNOWN_PROCESS_UNPROVEN")
        self.assertFalse(report["production_quiescence_proven"])

    def test_missing_identity_fails_closed(self):
        payload = {"ProcessId": 50, "Name": "CodeBridge.exe",
                   "ExecutablePath": None, "CreationDate": None}
        report = inspect_process_identities(runner=lambda *a, **k:
            SimpleNamespace(stdout=json.dumps(payload)))
        self.assertEqual(report["state"], "BLOCKED")
        self.assertEqual(report["unverified_count"], 1)

    def test_external_cli_intentionally_returns_non_authorizing_status(self):
        import subprocess
        script = Path(__file__).resolve().parents[1] / "rag_offline_pid_identity_cli.py"
        result = subprocess.run([sys.executable, str(script)], capture_output=True,
                                text=True, timeout=20)
        self.assertEqual(result.returncode, 2)
        report = json.loads(result.stdout)
        self.assertFalse(report["copy_authorized"])
        self.assertFalse(report["production_quiescence_proven"])

    def test_unreadable_inventory_blocks(self):
        def crash(*a, **k):
            raise ValueError("invalid output")
        report = inspect_process_identities(runner=crash)
        self.assertEqual(report["state"], "BLOCKED")
        self.assertFalse(report["identity_inventory_ok"])


if __name__ == "__main__":
    unittest.main()
