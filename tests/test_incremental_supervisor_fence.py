import tempfile
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
                issue_generation(path)
            self.assertFalse(path.exists())
            self.assertFalse(observe_generation(path, 1))

    def test_token_increments_across_restarts(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Path(tmp)/"supervisor_fence.sqlite3"
            lock=SupervisorLock(Path(tmp)/"lab.lock")
            with lock:
                first=issue_generation(store,lock_held=True)
                self.assertTrue(observe_generation(store,first))
            # Simulates a later process instance with new OS lock ownership
            with SupervisorLock(Path(tmp)/"lab.lock"):
                second=issue_generation(store,lock_held=True)
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
            with SupervisorLock(Path(tmp)/"lab.lock"):
                with self.assertRaises(ValueError):
                    issue_generation(store,lock_held=True)
            with closing(sqlite3.connect(store)) as db:
                self.assertEqual(db.execute("SELECT data FROM unrelated").fetchone()[0],"keep")

    def test_bad_token_is_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Path(tmp)/"supervisor_fence.sqlite3"
            with SupervisorLock(Path(tmp)/"lab.lock"):
                issued=issue_generation(store,lock_held=True)
            self.assertFalse(observe_generation(store,True))
            self.assertFalse(observe_generation(store,issued+1))
