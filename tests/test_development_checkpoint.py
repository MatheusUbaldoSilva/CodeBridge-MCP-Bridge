"""Persistence and validation checks for development-session checkpoints."""
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from author_mcp.development_checkpoint import DevelopmentCheckpoints


class DevelopmentCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "sessions.sqlite3"
        self.sid = "codebridge_" + "a" * 16
        self.store = DevelopmentCheckpoints(self.db)

    def test_persistent_resume_and_revision(self):
        self.assertIsNone(self.store.latest())
        first = self.store.save(self.sid, "coding", "test", ["implemented"], ["audit"])
        self.assertEqual(first["revision"], 1)
        recovered = DevelopmentCheckpoints(self.db).latest()
        self.assertEqual(recovered["next_step"], "test")
        self.assertEqual(recovered["completed"], ["implemented"])
        second = self.store.save(self.sid, "tested", "commit", stage="WRAP_UP_NOW")
        self.assertEqual(second["revision"], 2)
        self.assertEqual(self.store.latest(self.sid)["stage"], "WRAP_UP_NOW")

    def test_fail_closed_validation(self):
        with self.assertRaises(ValueError):
            self.store.save("bad", "x", "y")
        with self.assertRaises(ValueError):
            self.store.save(self.sid, "x", "y", stage="INVALID")
        with self.assertRaises(ValueError):
            self.store.save(self.sid, "x", "y", completed=["x" * 501])
        self.assertFalse(self.db.exists())


    def test_concurrent_writes_are_serialized(self):
        from concurrent.futures import ThreadPoolExecutor

        def write(number):
            return self.store.save(self.sid, f"step {number}", "continue")

        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(write, range(15)))

        resumed = DevelopmentCheckpoints(self.db).latest(self.sid)
        self.assertEqual(resumed["revision"], 15)

    def test_both_session_id_lengths_are_supported(self):
        legacy = "codebridge_" + "b" * 32
        self.assertEqual(self.store.save(legacy, "legacy", "next")["revision"], 1)
        with self.assertRaises(ValueError):
            self.store.save("codebridge_" + "a" * 15, "bad", "next")
        with self.assertRaises(ValueError):
            self.store.save("codebridge_" + "a" * 33, "bad", "next")


if __name__ == "__main__":
    unittest.main()
