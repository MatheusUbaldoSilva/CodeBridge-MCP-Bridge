"""Tests for complete NSIS pre-update backup without installer execution."""
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from installer.rag_p9b_installer_rollback_scope import (
    snapshot_installer_overwrites, verify_installer_rollback_snapshot,
    inspect_installer_snapshot_baseline, rehearse_installer_restore_scratch,
)


class NsisPreUpdateBackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.installed=self.root/"CodeBridge"
        self.installed.mkdir()
        self.exe=self.root/"installer.exe"
        self.exe.write_bytes(b"MZstub")
        self.zip7=self.root/"7z.exe"
        self.zip7.write_bytes(b"synthetic")
        self.backup=self.root/"backup.zip"
        self.existing=self.installed/"author_mcp"/"mcp_server.py"
        self.existing.parent.mkdir()
        self.existing.write_bytes(b"old-mcp")
        self.names=(
            "author_mcp/mcp_server.py",
            "rag/runtime/incremental_authorized_queue_bootstrap.py",
        ) + tuple("rag/runtime/synthetic_%03d.py" % i for i in range(98))

    def backup_call(self, **kwargs):
        with patch(
            "installer.rag_p9b_installer_rollback_scope.payload_file_list",
            return_value=self.names,
        ):
            return snapshot_installer_overwrites(
                self.exe,self.zip7,self.installed,self.backup,**kwargs,
            )

    def test_read_only_preview_does_not_create_archive(self):
        result=self.backup_call()
        self.assertEqual(result["state"],"INSTALLER_ROLLBACK_PLAN_ONLY")
        self.assertEqual(result["existing_files"],1)
        self.assertEqual(result["missing_files"],99)
        self.assertFalse(self.backup.exists())

    def test_backup_is_byte_exact_and_does_not_modify_installed(self):
        original=self.existing.read_bytes()
        report=self.backup_call(execute=True)
        self.assertEqual(report["state"],"INSTALLER_ROLLBACK_SNAPSHOT_CREATED")
        self.assertEqual(self.existing.read_bytes(),original)
        verify=verify_installer_rollback_snapshot(self.backup,self.installed)
        self.assertTrue(verify["verified"])
        self.assertEqual(verify["targets"],100)
        with ZipFile(self.backup) as archive:
            self.assertEqual(
                archive.read("old/author_mcp/mcp_server.py"), original,
            )
            manifest=json.loads(archive.read("manifest.json"))
            self.assertNotIn(
                "rag/runtime/incremental_authorized_queue_bootstrap.py",
                manifest["existing"],
            )
        self.assertFalse(
            (self.installed/"rag"/"runtime"/"incremental_authorized_queue_bootstrap.py").exists()
        )

    def test_no_overwrite_of_archive(self):
        self.backup.write_bytes(b"operator existing")
        result=self.backup_call(execute=True)
        self.assertFalse(result["created"])
        self.assertEqual(self.backup.read_bytes(),b"operator existing")

    def test_directory_in_place_of_file_denied(self):
        self.existing.unlink()
        self.existing.mkdir()
        result=self.backup_call(execute=True)
        self.assertEqual(result["reason"],"UNEXPECTED_INSTALLED_TARGET_TYPE")
        self.assertFalse(self.backup.exists())

    def test_rehearsal_in_scratch_matches_original_without_touching_installed(self):
        original=self.existing.read_bytes()
        self.backup_call(execute=True)
        self.assertTrue(inspect_installer_snapshot_baseline(
            self.backup,self.installed)["matches"])
        scratch=self.root/"scratch"
        stage=rehearse_installer_restore_scratch(self.backup,self.installed,scratch)
        self.assertEqual(stage["state"],"ISOLATED_INSTALLER_RESTORE_REHEARSED")
        self.assertTrue(stage["rehearsed"])
        self.assertEqual((scratch/"author_mcp/mcp_server.py").read_bytes(),original)
        self.assertFalse((scratch/"rag/runtime/incremental_authorized_queue_bootstrap.py").exists())
        self.assertEqual(self.existing.read_bytes(),original)

    def test_baseline_detects_modified_installed_file_or_new_file(self):
        self.backup_call(execute=True)
        self.existing.write_bytes(b"tampered")
        self.assertFalse(inspect_installer_snapshot_baseline(
            self.backup,self.installed)["matches"])
        self.existing.write_bytes(b"old-mcp")
        newfile=self.installed/"rag/runtime/incremental_authorized_queue_bootstrap.py"
        newfile.parent.mkdir(parents=True)
        newfile.write_bytes(b"unauthorized")
        self.assertFalse(inspect_installer_snapshot_baseline(
            self.backup,self.installed)["matches"])

    def test_restore_will_not_overwrite_existing_scratch(self):
        self.backup_call(execute=True)
        scratch=self.root/"scratch"
        scratch.mkdir()
        sentinel=scratch/"keep.txt"
        sentinel.write_text("keep")
        result=rehearse_installer_restore_scratch(
            self.backup,self.installed,scratch)
        self.assertFalse(result["rehearsed"])
        self.assertEqual(sentinel.read_text(),"keep")

    def test_invalid_archive_detected(self):
        self.backup.write_bytes(b"bad")
        self.assertFalse(
            verify_installer_rollback_snapshot(self.backup,self.installed)["verified"],
        )


if __name__=="__main__":
    unittest.main()
