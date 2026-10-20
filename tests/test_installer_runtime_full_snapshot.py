import tempfile
import unittest
from pathlib import Path

from installer.runtime_full_snapshot import (
    create_offline_runtime_snapshot,verify_offline_runtime_snapshot,
)

class FullRuntimeSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base=Path(self.temp.name)
        self.root=base/"CodeBridge"
        self.runtime=self.root/"runtime"/"python"
        (self.runtime/"Lib"/"site-packages").mkdir(parents=True)
        (self.runtime/"python.exe").write_bytes(b"exe")
        (self.runtime/"Lib"/"site-packages"/"module.py").write_text("ok")
        self.archive=base/"runtime-backup.zip"

    def test_default_dry_run_without_archive(self):
        state=create_offline_runtime_snapshot(self.root,self.archive)
        self.assertEqual(state["state"],"OFFLINE_SNAPSHOT_DRY_RUN")
        self.assertEqual(state["file_count"],2)
        self.assertFalse(self.archive.exists())

    def test_explicit_full_snapshot_integrity(self):
        state=create_offline_runtime_snapshot(
            self.root,self.archive,allow_offline_snapshot=True)
        self.assertEqual(state["state"],"OFFLINE_SNAPSHOT_CREATED")
        self.assertTrue(self.archive.exists())
        result=verify_offline_runtime_snapshot(self.archive)
        self.assertEqual(result["state"],"SNAPSHOT_CONTENT_VERIFIED")
        self.assertEqual(result["file_count"],2)
        self.assertFalse(result["restore_performed"])

    def test_missing_and_inside_destination_rejected(self):
        inside=self.root/"runtime-backup.zip"
        result=create_offline_runtime_snapshot(
            self.root,inside,allow_offline_snapshot=True)
        self.assertEqual(result["state"],"SNAPSHOT_PATH_INVALID")
        self.assertFalse(inside.exists())
        self.assertFalse(verify_offline_runtime_snapshot(inside)["verified"])

    def test_corrupted_archive_rejected(self):
        self.archive.write_bytes(b"not zip")
        result=verify_offline_runtime_snapshot(self.archive)
        self.assertEqual(result["state"],"SNAPSHOT_INTEGRITY_BLOCKED")

    def test_existing_archive_is_never_overwritten(self):
        self.archive.write_bytes(b"do-not-replace")
        result=create_offline_runtime_snapshot(
            self.root,self.archive,allow_offline_snapshot=True)
        self.assertEqual(result["state"],"SNAPSHOT_PATH_INVALID")
        self.assertEqual(self.archive.read_bytes(),b"do-not-replace")

    def test_runtime_symlink_rejected(self):
        target=Path(self.temp.name)/"external.txt"
        target.write_text("external")
        link=self.runtime/"redirect"
        try:
            link.symlink_to(target)
        except OSError:
            self.skipTest("Windows symlink permission unavailable")
        result=create_offline_runtime_snapshot(
            self.root,self.archive,allow_offline_snapshot=True)
        self.assertEqual(result["state"],"SYMLINK_IN_RUNTIME")
        self.assertFalse(self.archive.exists())

    def test_runtime_root_symlink_is_never_archived(self):
        from pathlib import Path
        other=Path(self.temp.name)/"external-runtime"
        other.mkdir()
        (other/"secret.txt").write_text("private")
        self.runtime.rename(self.root/"python-real")
        try:
            self.runtime.symlink_to(other, target_is_directory=True)
        except OSError:
            self.skipTest("Windows directory symlink permission unavailable")
        result=create_offline_runtime_snapshot(
            self.root,self.archive,allow_offline_snapshot=True)
        self.assertEqual(result["state"],"SNAPSHOT_PATH_INVALID")
        self.assertFalse(self.archive.exists())
