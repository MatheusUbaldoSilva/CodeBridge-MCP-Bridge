import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
from rag.runtime.offline_store_handle_probe import inspect_fixture_handles

@unittest.skipUnless(sys.platform == "win32", "Windows-only SQLite handle lab")
class SyntheticSQLiteSidecars(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="rag-lab02-b-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "codebridge-rag-generation-test"
        create_bundle(self.root, [("lab", "sqlite", "synthetic")])

    def assert_blocked(self, result):
        self.assertEqual(result["state"], "BLOCKED")
        self.assertFalse(result["copy_authorized"])
        self.assertFalse(result["all_handles_closed"])
        self.assertFalse(result["production_quiescence_proven"])

    def test_real_sqlite_wal_active_transaction(self):
        db = self.root / "rag_index.sqlite3"
        connection = sqlite3.connect(str(db), timeout=1)
        try:
            mode = connection.execute("PRAGMA journal_mode=WAL").fetchone()[0]
            self.assertEqual(mode.lower(), "wal")
            connection.execute("CREATE TABLE IF NOT EXISTS lab02_b (id INTEGER)")
            connection.commit()
            connection.execute("INSERT INTO lab02_b VALUES (1)")
            self.assertTrue((self.root / "rag_index.sqlite3-wal").exists())
            self.assertTrue((self.root / "rag_index.sqlite3-shm").exists())
            result = inspect_fixture_handles(self.root)
            self.assert_blocked(result)
            self.assertIn("SQLITE_SIDECAR_PRESENT", result["issues"])
            connection.rollback()
        finally:
            connection.close()
        result = inspect_fixture_handles(self.root)
        self.assertFalse(result["copy_authorized"])
        self.assertFalse(result["all_handles_closed"])

    def test_sidecars_block_without_live_connection(self):
        for suffix in ("-wal", "-shm", "-journal"):
            with self.subTest(suffix=suffix):
                sidecar = self.root / ("rag_index.sqlite3" + suffix)
                sidecar.write_bytes(b"synthetic")
                try:
                    result = inspect_fixture_handles(self.root)
                    self.assert_blocked(result)
                    self.assertIn("SQLITE_SIDECAR_PRESENT", result["issues"])
                finally:
                    sidecar.unlink()

    def test_readable_file_never_proves_quiescence(self):
        result = inspect_fixture_handles(self.root)
        self.assertEqual(result["state"], "LAB_HANDLES_READABLE_UNPROVEN")
        self.assertFalse(result["copy_authorized"])
        self.assertFalse(result["all_handles_closed"])
        self.assertFalse(result["production_quiescence_proven"])

if __name__ == "__main__":
    unittest.main()
