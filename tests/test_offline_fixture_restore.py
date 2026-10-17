"""Independent recovery of synthetic offline fixture snapshots."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
from rag.runtime.offline_fixture_snapshot import capture_fixture
from rag.runtime.offline_fixture_restore import restore_fixture_snapshot, OfflineFixtureRestoreError


class OfflineFixtureRestoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "codebridge-rag-generation-test"
        create_bundle(self.root, [("project-a", "file", "synthetic")])
        capture_fixture(self.root, "saved")

    def test_restore_produces_verified_unactivated_bundle(self):
        result = restore_fixture_snapshot(self.root, "saved", "recovered")
        self.assertEqual(result["state"], "LAB_FIXTURE_RESTORED_NOT_ACTIVATED")
        self.assertFalse(result["production_authorized"])
        self.assertEqual(result["verification"]["documents"], 1)
        self.assertTrue((self.root / "offline-fixture-restores" / "recovered" /
                         "snapshot" / "rag_index.sqlite3").is_file())
        self.assertFalse((self.root / "active-generation.json").exists())

    def test_standalone_restore_cli(self):
        import subprocess
        cli = Path(__file__).resolve().parents[1] / "rag_offline_fixture_restore_cli.py"
        args = [sys.executable, str(cli), "--fixture-root", str(self.root),
                "--backup-name", "saved", "--restore-name", "cli_restore"]
        blocked = subprocess.run(args, capture_output=True, text=True, timeout=20)
        self.assertNotEqual(blocked.returncode, 0)
        self.assertFalse((self.root / "offline-fixture-restores" / "cli_restore").exists())
        completed = subprocess.run(args + ["--lab-only"],
                                   capture_output=True, text=True, timeout=20)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["state"],
                         "LAB_FIXTURE_RESTORED_NOT_ACTIVATED")

    def test_backup_and_restore_do_not_change_active_pointer(self):
        import hashlib
        pointer = self.root / "active-generation.json"
        pointer.write_text('{"generation":"unchanged"}', encoding="utf-8")
        before = hashlib.sha256(pointer.read_bytes()).hexdigest()
        capture_fixture(self.root, "second")
        restore_fixture_snapshot(self.root, "second", "copy")
        self.assertEqual(hashlib.sha256(pointer.read_bytes()).hexdigest(), before)

    def test_two_project_restore_preserves_both_namespaces(self):
        import shutil
        multi_root = self.root.parent / "multiproject" / "codebridge-rag-generation-test"
        multi_root.parent.mkdir()
        create_bundle(multi_root, [("alpha", "one", "text-a"),
                                   ("beta", "two", "text-b")])
        capture_fixture(multi_root, "two_projects")
        report = restore_fixture_snapshot(multi_root, "two_projects", "both")
        self.assertEqual(report["verification"]["documents"], 2)
        self.assertEqual(report["verification"]["vectors"], 2)
        self.assertEqual(report["verification"]["manifest_entries"], 2)

    def test_restore_never_overwrites(self):
        restore_fixture_snapshot(self.root, "saved", "recovered")
        with self.assertRaises(OfflineFixtureRestoreError):
            restore_fixture_snapshot(self.root, "saved", "recovered")

    def test_modified_snapshot_is_rejected(self):
        report = self.root / "offline-fixture-backups" / "saved" / "report.json"
        data = json.loads(report.read_text(encoding="utf-8"))
        data["hashes"]["rag-index-manifest.json"] = "0"*64
        report.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(OfflineFixtureRestoreError):
            restore_fixture_snapshot(self.root, "saved", "recovered")
        self.assertFalse((self.root / "offline-fixture-restores" / "recovered").exists())

    def test_interrupted_copy_removes_only_temp_files(self):
        from unittest.mock import patch
        import rag.runtime.offline_fixture_restore as mod
        with patch.object(mod.shutil, "copytree", side_effect=OSError("simulated interrupted copy")):
            with self.assertRaises(OSError):
                restore_fixture_snapshot(self.root, "saved", "interrupted")
        restore_dir = self.root / "offline-fixture-restores"
        self.assertFalse((restore_dir / "interrupted").exists())
        self.assertEqual(list(restore_dir.glob(".restore-fixture-*")), [])
        self.assertTrue((self.root / "offline-fixture-backups" / "saved" / "report.json").is_file())

    def test_corrupted_snapshot_contents_are_rejected(self):
        manifest = (self.root / "offline-fixture-backups" / "saved" /
                    "snapshot" / "rag-index-manifest.json")
        manifest.write_text("forged", encoding="utf-8")
        with self.assertRaises(OfflineFixtureRestoreError):
            restore_fixture_snapshot(self.root, "saved", "corrupted")
        self.assertFalse((self.root / "offline-fixture-restores" / "corrupted").exists())

    def test_restore_rejects_sqlite_sidecar_in_backup(self):
        source=self.root/"offline-fixture-backups"/"saved"/"snapshot"
        (source/"rag_index.sqlite3-wal").write_bytes(b"synthetic")
        with self.assertRaises(OfflineFixtureRestoreError):
            restore_fixture_snapshot(self.root,"saved","unsafe")

    def test_restore_rejects_redirected_backup_ancestor(self):
        folder=self.root/"offline-fixture-backups"
        real=folder.with_name("original_backups")
        folder.rename(real)
        folder.symlink_to(real,target_is_directory=True)
        with self.assertRaises(OfflineFixtureRestoreError):
            restore_fixture_snapshot(self.root,"saved","redirected")
    def test_wrong_root_rejected(self):
        with self.assertRaises((ValueError, RuntimeError)):
            restore_fixture_snapshot(self.root.parent, "saved", "recovered")

    def test_same_named_restore_is_blocked_by_lock(self):
        from rag.runtime.generation_process_lock import generation_lock
        with generation_lock(self.root, "offline_capture", exclusive=True):
            with self.assertRaises(OfflineFixtureRestoreError):
                restore_fixture_snapshot(self.root, "saved", "locked")

if __name__ == "__main__":
    unittest.main()
