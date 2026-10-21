import tempfile
import subprocess
import sys
import time
from contextlib import closing
import unittest
from pathlib import Path

from rag.runtime.incremental_supervisor_fence import (
    issue_generation, observe_generation,
)
from rag.runtime.incremental_supervisor_lock import SupervisorLock


class DurableFenceTests(unittest.TestCase):
    def test_requires_lock_and_preserves_store_absence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"supervisor_fence.sqlite3"
            with self.assertRaises(PermissionError):
                issue_generation(path, lock=SupervisorLock(Path(tmp)/"lab.lock"))
            self.assertFalse(path.exists())
            self.assertFalse(observe_generation(path, 1))

    def test_token_increments_across_restarts(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Path(tmp)/"supervisor_fence.sqlite3"
            lock=SupervisorLock(Path(tmp)/"lab.lock")
            with lock:
                first=issue_generation(store,lock=lock)
                self.assertTrue(observe_generation(store,first))
            # Simulates a later process instance with new OS lock ownership
            with SupervisorLock(Path(tmp)/"lab.lock") as held:
                second=issue_generation(store,lock=held)
            self.assertEqual(second,first+1)
            self.assertFalse(observe_generation(store,first))
            self.assertTrue(observe_generation(store,second))

    def test_refuses_foreign_schema_without_overwriting(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as tmp:
            store=Path(tmp)/"supervisor_fence.sqlite3"
            with closing(sqlite3.connect(store)) as db:
                db.execute("CREATE TABLE unrelated(data TEXT)")
                db.execute("INSERT INTO unrelated VALUES ('keep')")
                db.commit()
            with SupervisorLock(Path(tmp)/"lab.lock") as held:
                with self.assertRaises(ValueError):
                    issue_generation(store,lock=held)
            with closing(sqlite3.connect(store)) as db:
                self.assertEqual(db.execute("SELECT data FROM unrelated").fetchone()[0],"keep")

    def test_bad_token_is_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Path(tmp)/"supervisor_fence.sqlite3"
            with SupervisorLock(Path(tmp)/"lab.lock") as held:
                issued=issue_generation(store,lock=held)
            self.assertFalse(observe_generation(store,True))
            self.assertFalse(observe_generation(store,issued+1))

    def test_cannot_issue_without_current_lock_ownership(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            store=root/"supervisor_fence.sqlite3"
            owner=SupervisorLock(root/"lab.lock")
            impostor=SupervisorLock(root/"lab.lock")
            with self.assertRaises(PermissionError):
                issue_generation(store,lock=owner)
            with owner:
                self.assertFalse(impostor.acquire())
                with self.assertRaises(PermissionError):
                    issue_generation(store,lock=impostor)
                issued=issue_generation(store,lock=owner)
            with self.assertRaises(PermissionError):
                issue_generation(store,lock=owner)
            self.assertTrue(observe_generation(store,issued))

    def test_refuses_lock_from_other_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            other=root/"foreign"
            other.mkdir()
            store=root/"supervisor_fence.sqlite3"
            with SupervisorLock(other/"lab.lock") as held:
                with self.assertRaisesRegex(PermissionError,"SCOPE_MISMATCH"):
                    issue_generation(store,lock=held)
            self.assertFalse(store.exists())

    def test_independent_process_cannot_issue_while_owner_holds_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            store=root/"supervisor_fence.sqlite3"
            script=(
                "import sys\n"
                "from pathlib import Path\n"
                "from rag.runtime.incremental_supervisor_lock import SupervisorLock\n"
                "from rag.runtime.incremental_supervisor_fence import issue_generation\n"
                "root=Path(sys.argv[1])\n"
                "with SupervisorLock(root/'lab.lock') as lock:\n"
                "    print(issue_generation(root/'supervisor_fence.sqlite3',lock=lock))\n"
            )
            with SupervisorLock(root/"lab.lock") as parent:
                first=issue_generation(store,lock=parent)
                denied=subprocess.run(
                    [sys.executable,"-c",script,str(root)],
                    cwd=str(Path(__file__).resolve().parents[1]),
                    capture_output=True,text=True,timeout=15,check=False,
                )
                self.assertNotEqual(denied.returncode,0)
                self.assertIn("SUPERVISOR_LOCK_BUSY_OR_UNAVAILABLE",denied.stderr)
                self.assertTrue(observe_generation(store,first))
            allowed=subprocess.run(
                [sys.executable,"-c",script,str(root)],
                cwd=str(Path(__file__).resolve().parents[1]),
                capture_output=True,text=True,timeout=15,check=False,
            )
            self.assertEqual(allowed.returncode,0,allowed.stderr)
            second=int(allowed.stdout.strip())
            self.assertEqual(second,first+1)
            self.assertFalse(observe_generation(store,first))
            self.assertTrue(observe_generation(store,second))

    def test_crashed_isolated_owner_releases_lock_and_fences_old_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            store=root/"supervisor_fence.sqlite3"
            ready=root/"child_ready.txt"
            script=(
                "import sys,time\n"
                "from pathlib import Path\n"
                "from rag.runtime.incremental_supervisor_lock import SupervisorLock\n"
                "from rag.runtime.incremental_supervisor_fence import issue_generation\n"
                "root=Path(sys.argv[1])\n"
                "with SupervisorLock(root/'lab.lock') as lock:\n"
                "    generation=issue_generation(root/'supervisor_fence.sqlite3',lock=lock)\n"
                "    (root/'child_ready.txt').write_text(str(generation),encoding='ascii')\n"
                "    time.sleep(30)\n"
            )
            process=subprocess.Popen(
                [sys.executable,"-c",script,str(root)],
                cwd=str(Path(__file__).resolve().parents[1]),
                stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,
            )
            try:
                deadline=time.monotonic()+10
                while not ready.exists() and process.poll() is None and time.monotonic()<deadline:
                    time.sleep(.03)
                self.assertTrue(ready.exists(),"synthetic child failed to start")
                first=int(ready.read_text(encoding='ascii'))
                self.assertTrue(observe_generation(store,first))
                competitor=SupervisorLock(root/"lab.lock")
                self.assertFalse(competitor.acquire())
                with self.assertRaises(PermissionError):
                    issue_generation(store,lock=competitor)
                process.kill()  # Strictly this test-owned isolated child, never GUI/MCP.
                process.wait(timeout=10)
                with SupervisorLock(root/"lab.lock") as successor:
                    second=issue_generation(store,lock=successor)
                self.assertEqual(second,first+1)
                self.assertFalse(observe_generation(store,first))
                self.assertTrue(observe_generation(store,second))
            finally:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=10)
                if process.stderr is not None:
                    process.stderr.close()
