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


if __name__ == "__main__":
    unittest.main()
