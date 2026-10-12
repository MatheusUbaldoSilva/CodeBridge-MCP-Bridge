"""Process inventory is diagnostic only, never production authorization."""
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rag.runtime.offline_quiescence_advisory import inspect_processes


class QuiescenceAdvisoryTests(unittest.TestCase):
    def test_codebridge_and_python_are_blockers(self):
        def fake(*args, **kwargs):
            return SimpleNamespace(stdout='"CodeBridge.exe","100","Console"\n"python.exe","99","Console"\n')
        result = inspect_processes(runner=fake)
        self.assertEqual(result["state"], "BLOCKED")
        self.assertEqual(result["suspect_names"], ["codebridge.exe", "python.exe"])
        self.assertFalse(result["copy_authorized"])

    def test_empty_suspects_never_authorize(self):
        result = inspect_processes(runner=lambda *a, **k:
            SimpleNamespace(stdout='"explorer.exe","11"\n"notepad.exe","22"\n'))
        self.assertEqual(result["state"], "UNPROVEN_QUIESCENCE")
        self.assertFalse(result["handles_verified"])
        self.assertFalse(result["copy_authorized"])

    def test_inventory_failure_fails_closed(self):
        def bad(*args, **kwargs):
            raise subprocess.TimeoutExpired("tasklist", 10)
        result = inspect_processes(runner=bad)
        self.assertEqual(result["state"], "BLOCKED")
        self.assertFalse(result["process_listing_ok"])
        self.assertFalse(result["copy_authorized"])

    def test_standalone_cli_intentionally_returns_blocking_exit(self):
        import json
        cli = Path(__file__).resolve().parents[1] / "rag_offline_quiescence_cli.py"
        result = subprocess.run([sys.executable, str(cli)], capture_output=True,
                                text=True, timeout=20)
        self.assertEqual(result.returncode, 2)
        report = json.loads(result.stdout)
        self.assertFalse(report["copy_authorized"])
        self.assertFalse(report["handles_verified"])

    def test_live_status_reports_no_authorization(self):
        result = inspect_processes()
        self.assertFalse(result["copy_authorized"])
        self.assertFalse(result["publication_authorized"])

if __name__ == "__main__":
    unittest.main()
