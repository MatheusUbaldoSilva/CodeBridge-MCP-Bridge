import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from rag.runtime.incremental_supervisor_lock import SupervisorLock


@unittest.skipUnless(os.name == "nt", "Windows msvcrt lock only")
class SupervisorLockTests(unittest.TestCase):
    def test_second_instance_denied_and_release_restores_access(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "supervisor.lock"
            first, second = SupervisorLock(path), SupervisorLock(path)
            self.assertTrue(first.acquire())
            self.assertFalse(second.acquire())
            self.assertTrue(first.release())
            self.assertTrue(second.acquire())
            self.assertTrue(second.release())

    def test_cross_process_exclusion_and_recovery_after_exit(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "supervisor.lock"
            command = [
                sys.executable, "-c",
                ("import sys,time;"
                 "from rag.runtime.incremental_supervisor_lock import SupervisorLock;"
                 "lock=SupervisorLock(sys.argv[1]);"
                 "print('ACQUIRED' if lock.acquire() else 'DENIED',flush=True);"
                 "time.sleep(4)"),
                str(path),
            ]
            child = subprocess.Popen(
                command, cwd=str(Path(__file__).resolve().parents[1]),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            try:
                self.assertEqual(child.stdout.readline().strip(), "ACQUIRED")
                self.assertFalse(SupervisorLock(path).acquire())
                child.wait(timeout=8)
                self.assertEqual(child.returncode, 0, child.stderr.read())
                survivor = SupervisorLock(path)
                self.assertTrue(survivor.acquire())
                self.assertTrue(survivor.release())
            finally:
                if child.poll() is None:
                    child.kill()
                    child.wait(timeout=8)
                if child.stdout:
                    child.stdout.close()
                if child.stderr:
                    child.stderr.close()

    def test_invalid_paths_rejected_without_creating_directories(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "not-created" / "supervisor.lock"
            self.assertFalse(SupervisorLock(target).acquire())
            self.assertFalse(target.parent.exists())
            self.assertFalse(SupervisorLock(Path(td) / "wrong.txt").acquire())

    def test_abrupt_child_exit_releases_os_lock(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "supervisor.lock"
            command = [
                sys.executable, "-c",
                ("import sys,time;"
                 "from rag.runtime.incremental_supervisor_lock import SupervisorLock;"
                 "lock=SupervisorLock(sys.argv[1]);"
                 "print('ACQUIRED' if lock.acquire() else 'DENIED',flush=True);"
                 "time.sleep(30)"),
                str(path),
            ]
            child = subprocess.Popen(
                command, cwd=str(Path(__file__).resolve().parents[1]),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            try:
                self.assertEqual(child.stdout.readline().strip(), "ACQUIRED")
                self.assertFalse(SupervisorLock(path).acquire())
                child.kill()
                child.wait(timeout=8)
                survivor = SupervisorLock(path)
                self.assertTrue(survivor.acquire())
                self.assertTrue(survivor.release())
            finally:
                if child.poll() is None:
                    child.kill()
                    child.wait(timeout=8)
                if child.stdout:
                    child.stdout.close()
                if child.stderr:
                    child.stderr.close()
