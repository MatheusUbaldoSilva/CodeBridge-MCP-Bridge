"""Laboratory supervisor test using only its own cooperatively stopped child.

The injected observer uses child.poll(), not a complete Windows process inventory;
a passing test cannot establish production quiescence.
"""
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rag.runtime.offline_pid_exit_supervisor import supervise_expected_exits


class LiveChildExitTests(unittest.TestCase):
    def test_child_observed_live_then_gracefully_exited(self):
        source = ("import sys;"
                  "print('READY',flush=True);"
                  "command=sys.stdin.readline().strip();"
                  "sys.exit(0 if command=='STOP' else 3)")
        child = subprocess.Popen(
            [sys.executable, "-c", source],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual(child.stdout.readline().strip(), "READY")
            identity = {
                "pid": child.pid,
                "created_at": "synthetic-child-created-in-this-test",
                "executable_fingerprint": "b" * 64,
            }
            count = [0]
            def observer():
                count[0] += 1
                if count[0] == 2:
                    child.stdin.write("STOP\n")
                    child.stdin.flush()
                    child.wait(timeout=8)
                rows = [identity] if child.poll() is None else []
                return {"identity_inventory_ok": True, "unverified_count": 0,
                        "verified_pids": rows}
            result = supervise_expected_exits(
                [identity], observer=observer, samples=5,
                pause_seconds=0, sleeper=lambda _: None)
            self.assertEqual(child.returncode, 0)
            self.assertEqual(result["state"], "EXPECTED_PIDS_ABSENT_UNPROVEN")
            self.assertEqual(result["observed_exit_pids"], [child.pid])
            self.assertGreaterEqual(result["samples_completed"], 3)
            self.assertFalse(result["copy_authorized"])
            self.assertFalse(result["all_handles_closed"])
            self.assertFalse(result["production_quiescence_proven"])
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
