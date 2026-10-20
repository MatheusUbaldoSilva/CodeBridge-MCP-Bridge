import tempfile
import unittest
from pathlib import Path

from installer.runtime_full_snapshot import create_offline_runtime_snapshot
from installer.runtime_restore_rehearsal import rehearse_runtime_restore


class RestoreRehearsalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.install = base / "installed"
        runtime = self.install / "runtime" / "python"
        runtime.mkdir(parents=True)
        (runtime / "python.exe").write_bytes(b"fixture-python")
        (runtime / "python313._pth").write_bytes(b"python313.zip\n.\n")
        self.archive = base / "backup.zip"
        result = create_offline_runtime_snapshot(
            self.install, self.archive, allow_offline_snapshot=True)
        self.assertTrue(result["archive_created"])
        self.scratch = base / "separate-restore"

    def test_dry_run_never_creates_destination(self):
        result = rehearse_runtime_restore(
            self.archive, self.scratch, self.install)
        self.assertEqual(result["state"], "RESTORE_REHEARSAL_DRY_RUN")
        self.assertFalse(self.scratch.exists())

    def test_separate_restore_hash_and_content(self):
        result = rehearse_runtime_restore(
            self.archive, self.scratch, self.install, execute=True)
        self.assertEqual(result["state"], "ISOLATED_RUNTIME_RESTORE_REHEARSED")
        self.assertTrue(result["rehearsed"])
        self.assertEqual(
            (self.scratch / "runtime" / "python" / "python.exe").read_bytes(),
            b"fixture-python",
        )
        self.assertEqual(
            (self.install / "runtime" / "python" / "python.exe").read_bytes(),
            b"fixture-python",
        )

    def test_refuse_install_root_and_ancestor(self):
        for target in (self.install, self.install/"runtime"/"restore",
                       self.install.parent):
            result = rehearse_runtime_restore(
                self.archive, target, self.install, execute=True)
            self.assertEqual(result["state"], "RESTORE_TARGET_UNSAFE")

    def test_reject_corrupt_zip_without_creating_target(self):
        self.archive.write_bytes(b"bad zip")
        result = rehearse_runtime_restore(
            self.archive, self.scratch, self.install, execute=True)
        self.assertEqual(result["state"], "SNAPSHOT_NOT_VERIFIED")
        self.assertFalse(self.scratch.exists())

    def test_tampered_archive_is_rejected_before_restore(self):
        import json
        from zipfile import ZipFile, ZIP_DEFLATED
        altered = Path(self.temp.name) / "tampered.zip"
        with ZipFile(self.archive) as original:
            with ZipFile(altered, "w", compression=ZIP_DEFLATED) as edited:
                for item in original.namelist():
                    data = original.read(item)
                    if item.endswith("python.exe"):
                        data = b"tampered-python"
                    edited.writestr(item, data)
        result = rehearse_runtime_restore(
            altered, self.scratch, self.install, execute=True)
        self.assertEqual(result["state"], "SNAPSHOT_NOT_VERIFIED")
        self.assertFalse(self.scratch.exists())

    def test_existing_restore_target_is_never_overwritten(self):
        self.scratch.mkdir()
        marker = self.scratch / "keep.txt"
        marker.write_text("unchanged")
        result = rehearse_runtime_restore(
            self.archive, self.scratch, self.install, execute=True)
        self.assertEqual(result["state"], "RESTORE_TARGET_UNAVAILABLE")
        self.assertEqual(marker.read_text(), "unchanged")

    def test_cli_defaults_to_dry_run(self):
        import subprocess
        import sys
        root=Path(__file__).resolve().parents[1]
        command=[sys.executable,"-m","installer.runtime_restore_rehearsal",
                 "--archive",str(self.archive),"--scratch-root",str(self.scratch),
                 "--install-root",str(self.install)]
        result=subprocess.run(command,cwd=root,capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn("RESTORE_REHEARSAL_DRY_RUN",result.stdout)
        self.assertFalse(self.scratch.exists())

    def test_rehearsal_rejects_destination_outside_os_temp(self):
        import tempfile
        import os
        from pathlib import Path
        outside = Path.home() / "CodeBridge-Should-Not-Be-Created"
        if outside.is_relative_to(Path(tempfile.gettempdir()).resolve()):
            self.skipTest("Home directory within temporary directory")
        result = rehearse_runtime_restore(
            self.archive, outside, self.install, execute=True)
        self.assertEqual(result["state"], "RESTORE_TARGET_UNSAFE")
        self.assertFalse(outside.exists())
