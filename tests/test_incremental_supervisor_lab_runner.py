import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from rag.runtime.incremental_supervisor_lab_runner import SupervisorLabRunner


@unittest.skipUnless(os.name == "nt", "Windows locking laboratory")
class SupervisorLabRunnerTests(unittest.TestCase):
    def test_successful_inert_cycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            observed = []
            runner = SupervisorLabRunner(Path(tmp) / "lab.lock")
            result = runner.run_once(lambda: observed.append("executed"))
            self.assertEqual(result["state"], "LAB_CYCLE_COMPLETE")
            self.assertEqual(observed, ["executed"])
            self.assertEqual(result["supervisor_state"], "STOPPED")
            self.assertFalse(result["worker_started"])
            self.assertFalse(result["safe_to_publish"])

    def test_failure_requires_explicit_reset(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = SupervisorLabRunner(Path(tmp) / "lab.lock")
            def failure():
                raise RuntimeError("synthetic")
            first = runner.run_once(failure)
            self.assertEqual(first["state"], "LAB_CALLBACK_FAILED")
            self.assertEqual(first["supervisor_state"], "FAILED")
            self.assertEqual(runner.run_once(lambda: None)["state"],
                             "ALREADY_ACTIVE_OR_FAILED")
            self.assertTrue(runner.reset_after_failure())
            self.assertEqual(runner.run_once(lambda: None)["state"],
                             "LAB_CYCLE_COMPLETE")

    def test_missing_callback_creates_no_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "lab.lock"
            runner = SupervisorLabRunner(target)
            self.assertEqual(runner.run_once()["state"], "NO_LAB_CALLBACK")
            self.assertFalse(target.exists())

    def test_two_independent_processes_cannot_overlap(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "lab.lock"
            child_code = (
                "import sys,time;"
                "from rag.runtime.incremental_supervisor_lock import SupervisorLock;"
                "lock=SupervisorLock(sys.argv[1]);"
                "print('LOCKED' if lock.acquire() else 'DENIED',flush=True);"
                "time.sleep(3)"
            )
            child = subprocess.Popen(
                [sys.executable, "-c", child_code, str(target)],
                cwd=str(Path(__file__).resolve().parents[1]),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                self.assertEqual(child.stdout.readline().strip(), "LOCKED")
                runner = SupervisorLabRunner(target)
                self.assertEqual(runner.run_once(lambda: None)["state"],
                                 "LOCK_UNAVAILABLE")
                child.wait(timeout=8)
                self.assertEqual(child.returncode, 0)
                self.assertEqual(runner.run_once(lambda: None)["state"],
                                 "LAB_CYCLE_COMPLETE")
            finally:
                if child.poll() is None:
                    child.kill()
                    child.wait(timeout=8)
                child.stdout.close()
                child.stderr.close()
