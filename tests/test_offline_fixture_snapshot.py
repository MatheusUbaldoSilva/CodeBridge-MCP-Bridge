"""Offline snapshot isolated fixture tests."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
from rag.runtime.offline_fixture_snapshot import capture_fixture, OfflineFixtureError


class OfflineFixtureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "codebridge-rag-generation-test"
        create_bundle(self.root, [("a", "file", "content")])

    def test_capture_does_not_touch_source(self):
        result = capture_fixture(self.root, "first")
        self.assertEqual(result["state"], "LAB_FIXTURE_SNAPSHOT_ONLY")
        self.assertFalse(result["production_authorized"])
        self.assertTrue((self.root / "offline-fixture-backups" / "first" / "snapshot" / "qdrant").is_dir())

    def test_no_overwrite(self):
        capture_fixture(self.root, "first")
        with self.assertRaises(OfflineFixtureError):
            capture_fixture(self.root, "first")

    def test_wrong_root_blocked(self):
        with self.assertRaises(OfflineFixtureError):
            capture_fixture(self.root.parent, "first")

    def test_wal_blocks(self):
        (self.root / "rag_index.sqlite3-wal").write_bytes(b"pending")
        with self.assertRaises(OfflineFixtureError):
            capture_fixture(self.root, "first")

    def test_symlink_qdrant_blocked(self):
        import shutil
        shutil.rmtree(self.root / "qdrant")
        (self.root / "qdrant").symlink_to(self.root.parent, target_is_directory=True)
        with self.assertRaises(OfflineFixtureError):
            capture_fixture(self.root, "first")


if __name__ == "__main__":
    unittest.main()
