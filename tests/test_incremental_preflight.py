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
                con.execute("CREATE TABLE rag_documents(project_id TEXT, path TEXT, sha256 TEXT)")
                con.execute("INSERT INTO rag_documents VALUES (?, ?, ?)", ("a", "existing.md", None))
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

    def test_modified_unchanged_and_project_isolation(self):
        from rag.chunking.provenance import source_sha256
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'same.md').write_text('original', encoding='utf-8')
            (root / 'changed.md').write_text('new text', encoding='utf-8')
            db = root / 'index.sqlite3'
            con = sqlite3.connect(db)
            try:
                con.execute('CREATE TABLE rag_documents(project_id TEXT, path TEXT, sha256 TEXT)')
                con.executemany('INSERT INTO rag_documents VALUES (?, ?, ?)', [
                    ('a', 'same.md', source_sha256('original')),
                    ('a', 'changed.md', source_sha256('old text')),
                    ('b', 'other.md', source_sha256('else')),
                ])
                con.commit()
            finally:
                con.close()
            before = db.read_bytes()
            result = assess_incremental_plan({
                'project_id': 'a', 'project_root': str(root),
                'candidates': [{'path': 'same.md'}, {'path': 'changed.md'},
                               {'path': 'other.md'}],
            }, database=db)
            self.assertEqual(result['unchanged_files'], ['same.md'])
            self.assertEqual(result['modified_files'], ['changed.md'])
            self.assertEqual(result['new_files'], ['other.md'])
            self.assertFalse(result['safe_to_publish'])
            self.assertEqual(db.read_bytes(), before)

    def test_missing_db_and_bad_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = assess_incremental_plan({
                "project_id": "fresh", "candidates": [{"path": "note.md"}],
            }, database=Path(tmp) / "missing.sqlite3")
            self.assertEqual(result["new_count"], 1)
            with self.assertRaises(ValueError):
                assess_incremental_plan({"project_id": "a", "candidates": ["invalid"]},
                                        database=Path(tmp) / "missing.sqlite3")
