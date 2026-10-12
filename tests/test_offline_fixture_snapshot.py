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

    def test_snapshot_verified_in_separate_python_process(self):
        import json
        import subprocess
        result = capture_fixture(self.root, "verified")
        target = self.root / "offline-fixture-backups" / "verified"
        self.assertTrue(result["hashes"])
        self.assertEqual(result["verification"]["documents"], 1)
        self.assertEqual(result["verification"]["vectors"], 1)
        report = json.loads((target / "report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["hashes"], result["hashes"])
        code = ("import json,sys;"
                "from rag.runtime.incremental_bundle_validate import validate_incremental_bundle;"
                "print(json.dumps(validate_incremental_bundle(sys.argv[1])))")
        proc = subprocess.run([sys.executable, "-c", code, str(target / "snapshot")],
                              capture_output=True, text=True, cwd=str(Path(__file__).resolve().parents[1]),
                              timeout=20)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["state"], "VALIDATED_OFFLINE_NOT_PUBLISHED")

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

    def test_competing_process_lock_blocks_capture(self):
        from rag.runtime.generation_process_lock import generation_lock
        with generation_lock(self.root, "offline_capture", exclusive=True):
            with self.assertRaises(OfflineFixtureError):
                capture_fixture(self.root, "locked")
        self.assertFalse((self.root / "offline-fixture-backups" / "locked").exists())

    def test_changed_source_during_copy_is_rejected(self):
        from unittest.mock import patch
        import rag.runtime.offline_fixture_snapshot as snapshot
        original = snapshot.shutil.copytree
        def tamper(src, dst, *args, **kwargs):
            result = original(src, dst, *args, **kwargs)
            (self.root / "rag-index-manifest.json").write_text("changed")
            return result
        with patch.object(snapshot.shutil, "copytree", side_effect=tamper):
            with self.assertRaises(OfflineFixtureError):
                capture_fixture(self.root, "tampered")
        self.assertFalse((self.root / "offline-fixture-backups" / "tampered").exists())

    def test_internal_qdrant_symlink_rejected(self):
        (self.root / "qdrant" / "outside").symlink_to(self.root.parent, target_is_directory=True)
        with self.assertRaises(OfflineFixtureError):
            capture_fixture(self.root, "symlinked")

    def test_symlink_qdrant_blocked(self):
        import shutil
        shutil.rmtree(self.root / "qdrant")
        (self.root / "qdrant").symlink_to(self.root.parent, target_is_directory=True)
        with self.assertRaises(OfflineFixtureError):
            capture_fixture(self.root, "first")


if __name__ == "__main__":
    unittest.main()
