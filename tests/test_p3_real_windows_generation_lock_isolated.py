import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rag.runtime import production_generation_lock as lock


CHILD = """
import sys
from pathlib import Path
from unittest.mock import patch
from rag.runtime import production_generation_lock as lock
path = Path(sys.argv[1])
exclusive = sys.argv[2] == 'exclusive'
try:
    with patch.object(lock, 'resolve_rag_sqlite_path', return_value=path):
        with lock.production_generation_lock(exclusive=exclusive):
            print('ACQUIRED')
except lock.ProductionGenerationBusy:
    print('BUSY_CONFIRMED')
"""


@unittest.skipUnless(sys.platform == "win32", "Windows LockFileEx required")
class RealWindowsGenerationLockTests(unittest.TestCase):
    def run_other_process(self, path, mode):
        result = subprocess.run(
            [sys.executable, "-c", CHILD, str(path), mode],
            cwd=str(Path(__file__).resolve().parents[1]),
            capture_output=True, text=True, timeout=18)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_shared_lock_blocks_exclusive_then_releases(self):
        with tempfile.TemporaryDirectory(prefix="codebridge-p3-lock-") as tmp:
            state = Path(tmp) / "CodeBridge" / "rag"
            state.mkdir(parents=True)
            db = state / "rag_index.sqlite3"
            with patch.object(lock, "resolve_rag_sqlite_path", return_value=db):
                with lock.production_generation_lock(exclusive=False):
                    self.assertIn("BUSY_CONFIRMED", self.run_other_process(db, "exclusive"))
                self.assertIn("ACQUIRED", self.run_other_process(db, "exclusive"))

    def test_production_reader_pin_remains_held_across_yield(self):
        from rag.runtime import production_generation_read as reader
        with tempfile.TemporaryDirectory(prefix="codebridge-p3-reader-") as tmp:
            state = Path(tmp) / "CodeBridge" / "rag"
            state.mkdir(parents=True)
            db = state / "rag_index.sqlite3"
            db.write_bytes(b"fixture")
            manifest = state / "rag-index-manifest.json"
            manifest.write_text("{}", encoding="utf-8")
            qdrant = state / "qdrant"
            qdrant.mkdir()
            with patch.object(lock, "resolve_rag_sqlite_path", return_value=db), patch.object(
                reader, "resolve_rag_sqlite_path", return_value=db
            ), patch.object(reader, "resolve_rag_manifest_path", return_value=manifest), patch.object(
                reader, "resolve_qdrant_local_path", return_value=qdrant
            ):
                with reader.production_generation_read() as pinned:
                    self.assertEqual(pinned.generation, "legacy")
                    self.assertEqual(pinned.sqlite, db.resolve())
                    self.assertIn("BUSY_CONFIRMED", self.run_other_process(db, "exclusive"))
                self.assertIn("ACQUIRED", self.run_other_process(db, "exclusive"))

    def test_exclusive_blocks_reader_then_releases(self):
        with tempfile.TemporaryDirectory(prefix="codebridge-p3-lock-") as tmp:
            state = Path(tmp) / "CodeBridge" / "rag"
            state.mkdir(parents=True)
            db = state / "rag_index.sqlite3"
            with patch.object(lock, "resolve_rag_sqlite_path", return_value=db):
                with lock.production_generation_lock(exclusive=True):
                    self.assertIn("BUSY_CONFIRMED", self.run_other_process(db, "shared"))
                self.assertIn("ACQUIRED", self.run_other_process(db, "shared"))
