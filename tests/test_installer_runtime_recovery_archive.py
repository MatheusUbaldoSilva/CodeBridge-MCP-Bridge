import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile
from installer.runtime_recovery_archive import prepare_runtime_recovery, FILES

class RecoveryArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base=Path(self.temp.name)
        self.root=base/"installed"
        for name in FILES:
            file=self.root/name
            file.parent.mkdir(parents=True,exist_ok=True)
            file.write_text("fixture-"+name,encoding="utf-8")
        self.out=base/"recovery.zip"

    def test_dry_run_does_not_create_archive(self):
        result=prepare_runtime_recovery(self.root,self.out)
        self.assertEqual(result["state"],"RECOVERY_DRY_RUN")
        self.assertFalse(self.out.exists())
        self.assertFalse(result["will_include_secrets"])
        self.assertFalse(result["full_rollback_available"])
        self.assertEqual(result["archive_scope"],"METADATA_ONLY")

    def test_explicit_archive_only_contains_allowlisted_metadata(self):
        result=prepare_runtime_recovery(self.root,self.out,create_archive=True)
        self.assertTrue(result["archive_created"])
        self.assertFalse(result["full_rollback_available"])
        with ZipFile(self.out) as archive:
            self.assertEqual(set(archive.namelist()),set(FILES)|{"SHA256.json"})
            self.assertEqual(json.loads(archive.read("SHA256.json")),result["files"])
        again=prepare_runtime_recovery(self.root,self.out,create_archive=True)
        self.assertEqual(again["state"],"INVALID_ARCHIVE_DESTINATION")

    def test_archive_cannot_be_created_inside_installation(self):
        result=prepare_runtime_recovery(self.root,self.root/"backup.zip",
                                        create_archive=True)
        self.assertEqual(result["state"],"INVALID_ARCHIVE_DESTINATION")
        self.assertFalse((self.root/"backup.zip").exists())

    def test_missing_file_rejected(self):
        (self.root/"version.json").unlink()
        result=prepare_runtime_recovery(self.root,self.out,create_archive=True)
        self.assertEqual(result["state"],"RUNTIME_METADATA_MISSING")
        self.assertFalse(self.out.exists())
