"""Read-only incremental safety checks, never touching production."""
import sqlite3
import tempfile
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rag.runtime.incremental_preflight import assess_incremental_plan


class IncrementalPreflightTests(unittest.TestCase):
    def test_new_and_existing_and_no_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "index.sqlite3"
            con = sqlite3.connect(db)
            try:
                con.execute("CREATE TABLE rag_documents(project_id TEXT, path TEXT)")
                con.execute("INSERT INTO rag_documents VALUES (?, ?)", ("a", "existing.md"))
                con.commit()
            finally:
                con.close()
            original = db.read_bytes()
            result = assess_incremental_plan({
                "project_id": "a",
                "candidates": [{"path": "existing.md"}, {"path": "new.md"}],
            }, database=db)
            self.assertEqual(result["new_files"], ["new.md"])
            self.assertEqual(result["existing_files"], ["existing.md"])
            self.assertFalse(result["safe_to_publish"])
            self.assertEqual(db.read_bytes(), original)

    def test_missing_db_and_bad_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = assess_incremental_plan({
                "project_id": "fresh", "candidates": [{"path": "note.md"}],
            }, database=Path(tmp) / "missing.sqlite3")
            self.assertEqual(result["new_count"], 1)
            with self.assertRaises(ValueError):
                assess_incremental_plan({"project_id": "a", "candidates": ["invalid"]},
                                        database=Path(tmp) / "missing.sqlite3")
