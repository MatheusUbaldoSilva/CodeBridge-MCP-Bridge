import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from installer.rag_p9b_nsis_file_e2e_lab import run_file_scope_lab


class FileScopeTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=Path(t.name)
        self.installed=self.root/"installed"
        self.installed.mkdir()
        self.lab=self.root/"scratch"
        self.zip=self.root/"baseline.zip"
        old=b"previous content"
        meta={"bytes":len(old),"sha256":hashlib.sha256(old).hexdigest()}
        with ZipFile(self.zip,"w") as z:
            z.writestr("manifest.json",json.dumps({
                "targets":["rag/old.py","rag/new.py"],
                "existing":{"rag/old.py":meta}}))
            z.writestr("old/rag/old.py",old)

    @patch("installer.rag_p9b_nsis_file_e2e_lab.verify_installer_rollback_snapshot",
           return_value={"verified":True})
    def test_restore_and_delete_new_file(self,_):
        r=run_file_scope_lab(self.zip,self.installed,self.lab)
        self.assertEqual(r["state"],"NSIS_FILE_SCOPE_LAB_RECOVERED")
        self.assertEqual(r["old_files_restored"],1)
        self.assertEqual(r["new_targets_removed"],1)
        self.assertEqual((self.lab/"rag"/"old.py").read_bytes(),b"previous content")
        self.assertFalse((self.lab/"rag"/"new.py").exists())

    @patch("installer.rag_p9b_nsis_file_e2e_lab.verify_installer_rollback_snapshot",
           return_value={"verified":True})
    def test_existing_lab_refused(self,_):
        self.lab.mkdir()
        r=run_file_scope_lab(self.zip,self.installed,self.lab)
        self.assertEqual(r["reason"],"LAB_PATH_INVALID")

    @patch("installer.rag_p9b_nsis_file_e2e_lab.verify_installer_rollback_snapshot",
           return_value={"verified":False})
    def test_bad_snapshot_refused(self,_):
        r=run_file_scope_lab(self.zip,self.installed,self.lab)
        self.assertEqual(r["reason"],"SNAPSHOT_UNVERIFIED")
        self.assertFalse(self.lab.exists())


if __name__=="__main__":
    unittest.main()
