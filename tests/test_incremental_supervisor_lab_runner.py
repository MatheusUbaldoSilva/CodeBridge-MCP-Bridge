import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from rag.runtime.incremental_supervisor_lab_runner import SupervisorLabRunner
from rag.runtime.incremental_supervisor_fence import observe_generation


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

    def test_explicit_durable_runner_issues_distinct_tokens(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            store=root/"supervisor_fence.sqlite3"
            first=SupervisorLabRunner(root/"lab.lock",durable_store=store)
            result=first.run_once(lambda: None)
            self.assertEqual(result["state"],"LAB_CYCLE_COMPLETE")
            g1=result["durable_generation"]
            self.assertEqual(g1,1)
            self.assertTrue(observe_generation(store,g1))
            second=SupervisorLabRunner(root/"lab.lock",durable_store=store)
            result2=second.run_once(lambda: None)
            self.assertEqual(result2["state"],"LAB_CYCLE_COMPLETE")
            self.assertEqual(result2["durable_generation"],g1+1)
            self.assertFalse(observe_generation(store,g1))
            self.assertTrue(observe_generation(store,g1+1))
            self.assertFalse(result2["safe_to_publish"])

    def test_runner_denies_foreign_store_before_callback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            foreign=root/"other"
            foreign.mkdir()
            store=foreign/"supervisor_fence.sqlite3"
            executed=[]
            runner=SupervisorLabRunner(root/"lab.lock",durable_store=store)
            result=runner.run_once(lambda: executed.append(True))
            self.assertEqual(result["state"],"DURABLE_FENCE_UNAVAILABLE")
            self.assertEqual(result["supervisor_state"],"STOPPED")
            self.assertEqual(executed,[])
            self.assertFalse(store.exists())
