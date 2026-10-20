import hashlib
import tempfile
import unittest
from pathlib import Path

from installer.runtime_full_restore_preflight import inspect_full_restore_readiness


class FullRestoreReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        home = Path(self.temp.name)
        self.root = home / "installed"
        runtime = self.root / "runtime" / "python"
        runtime.mkdir(parents=True)
        (runtime / "python.exe").write_bytes(b"python-fixture")
        self.installer = home / "setup.exe"
        self.installer.write_bytes(b"installer-fixture")
        self.digest = home / "setup.sha256"
        self.digest.write_text(
            hashlib.sha256(b"installer-fixture").hexdigest()
            + "  setup.exe\n", encoding="ascii"
        )
        self.destination = home / "backup.zip"

    def test_checks_can_pass_without_claiming_full_rollback(self):
        result = inspect_full_restore_readiness(
            self.root, self.installer, self.digest, self.destination)
        self.assertEqual(result["state"], "RESTORE_PREREQUISITES_PRESENT")
        self.assertFalse(result["verified"])
        self.assertTrue(result["installer_checksum_matches"])
        self.assertFalse(result["installation_modified"])
        self.assertFalse(self.destination.exists())

    def test_corrupt_installer_hash_rejects_preflight(self):
        self.digest.write_text("0" * 64 + "  setup.exe\n", encoding="ascii")
        result = inspect_full_restore_readiness(
            self.root, self.installer, self.digest, self.destination)
        self.assertEqual(result["state"], "FULL_RESTORE_NOT_VERIFIED")
        self.assertFalse(result["installer_checksum_matches"])

    def test_backup_inside_program_files_rejected(self):
        result = inspect_full_restore_readiness(
            self.root, self.installer, self.digest, self.root / "backup.zip")
        self.assertFalse(result["backup_outside_installation"])
        self.assertFalse(result["verified"])

    def test_missing_backup_parent_never_creates_directory(self):
        target = Path(self.temp.name) / "does-not-exist" / "backup.zip"
        result = inspect_full_restore_readiness(
            self.root, self.installer, self.digest, target)
        self.assertEqual(result["state"], "FULL_RESTORE_NOT_VERIFIED")
        self.assertFalse(target.parent.exists())
