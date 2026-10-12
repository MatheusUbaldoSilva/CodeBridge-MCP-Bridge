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

    def test_standalone_cli_laboratory_only(self):
        import json
        import subprocess
        script = Path(__file__).resolve().parents[1] / "rag_offline_fixture_cli.py"
        base = [sys.executable, str(script), "--fixture-root", str(self.root),
                "--backup-name", "from_cli"]
        no_flag = subprocess.run(base, capture_output=True, text=True, timeout=20)
        self.assertNotEqual(no_flag.returncode, 0)
        self.assertFalse((self.root / "offline-fixture-backups" / "from_cli").exists())
        okay = subprocess.run(base + ["--lab-only"], capture_output=True, text=True, timeout=20)
        self.assertEqual(okay.returncode, 0, okay.stderr)
        self.assertEqual(json.loads(okay.stdout)["state"], "LAB_FIXTURE_SNAPSHOT_ONLY")
        another = subprocess.run(base + ["--lab-only"], capture_output=True, text=True, timeout=20)
        self.assertEqual(another.returncode, 2)
        self.assertEqual(json.loads(another.stdout)["state"], "BLOCKED")

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

    def test_windows_open_writer_blocks_snapshot(self):
        import subprocess
        import time
        code = ("import sys,time;"
                "f=open(sys.argv[1],'r+b',buffering=0);"
                "print('READY',flush=True);"
                "time.sleep(10)")
        writer = subprocess.Popen([sys.executable, "-c", code,
                                   str(self.root / "rag_index.sqlite3")],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual(writer.stdout.readline().strip(), "READY")
            with self.assertRaises(OfflineFixtureError):
                capture_fixture(self.root, "open_writer")
            self.assertFalse((self.root / "offline-fixture-backups" / "open_writer").exists())
        finally:
            writer.terminate()
            writer.communicate(timeout=10)

    def test_hardlinked_sqlite_is_rejected(self):
        import os
        shared = self.root.parent / "shared-synthetic.sqlite3"
        original = self.root / "rag_index.sqlite3"
        original.rename(shared)
        os.link(shared, original)
        with self.assertRaises(OfflineFixtureError):
            capture_fixture(self.root, "linked")

    def test_hardlinked_qdrant_file_is_rejected(self):
        import os
        source = next(p for p in (self.root / "qdrant").rglob("*") if p.is_file())
        os.link(source, source.with_name(source.name + ".hardlink"))
        with self.assertRaises(OfflineFixtureError):
            capture_fixture(self.root, "linked_vector")

    def test_symlink_qdrant_blocked(self):
        import shutil
        shutil.rmtree(self.root / "qdrant")
        (self.root / "qdrant").symlink_to(self.root.parent, target_is_directory=True)
        with self.assertRaises(OfflineFixtureError):
            capture_fixture(self.root, "first")


if __name__ == "__main__":
    unittest.main()
