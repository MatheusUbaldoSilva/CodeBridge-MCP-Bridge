import json, subprocess, sys, unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CLI = REPO / "rag_offline_scoped_observer_cli.py"

class ScopedObserverCliTests(unittest.TestCase):
    def test_requires_explicit_lab_only(self):
        result = subprocess.run([sys.executable, str(CLI), "--pid", "123"],
                                capture_output=True, text=True, timeout=8)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("copy_authorized", result.stdout)
    @unittest.skipUnless(sys.platform == "win32", "Windows-only scoped CIM")
    def test_live_synthetic_child_is_readonly_and_non_authorizing(self):
        child = subprocess.Popen([sys.executable, "-c",
                                  "import sys;print('READY',flush=True);sys.stdin.readline()"],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual(child.stdout.readline().strip(), "READY")
            result = subprocess.run([sys.executable, str(CLI), "--lab-only",
                                     "--pid", str(child.pid)],
                                    capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 2)
            report = json.loads(result.stdout)
            self.assertEqual(report["state"], "SCOPED_CIM_OBSERVATION_UNPROVEN")
            self.assertEqual([row["pid"] for row in report["verified_pids"]],
                             [child.pid])
            self.assertFalse(report["copy_authorized"])
            self.assertFalse(report["all_handles_closed"])
            self.assertNotIn("ExecutablePath", result.stdout)
            self.assertNotIn("CommandLine", result.stdout)
        finally:
            if child.poll() is None:
                child.stdin.write("STOP\n")
                child.stdin.flush()
                child.wait(timeout=8)
            child.stdin.close()
            child.stdout.close()
            child.stderr.close()
if __name__ == "__main__":
    unittest.main()
