import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile
from installer.rag_p9b_file_restore_executor_lab import restore_files_in_lab

class FileRestoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.installed=self.root/"installed";self.installed.mkdir()
        self.lab=self.root/"scratch";self.lab.mkdir()
        (self.lab/"pkg").mkdir()
        (self.lab/"pkg"/"old.py").write_bytes(b"changed")
        (self.lab/"pkg"/"new.py").write_bytes(b"P9B_LAB_INSTALLER_CREATED_V1")
        self.zip=self.root/"snapshot.zip"
        old=b"before"
        with ZipFile(self.zip,"w") as z:
            z.writestr("manifest.json",json.dumps({"targets":["pkg/old.py","pkg/new.py"],
                "existing":{"pkg/old.py":{"sha256":hashlib.sha256(old).hexdigest()}}}))
            z.writestr("old/pkg/old.py",old)
        self.sha=hashlib.sha256(self.zip.read_bytes()).hexdigest()
    def go(self,**kwargs):
        params=dict(snapshot=self.zip,installed=self.installed,lab_root=self.lab,
                    expected_sha256=self.sha,
                    snapshot_probe=lambda *a:{"verified":True})
        params.update(kwargs)
        return restore_files_in_lab(**params)
    def test_restores_old_removes_new(self):
        r=self.go()
        self.assertEqual(r["state"],"FILE_RESTORE_LAB_VERIFIED")
        self.assertEqual((self.lab/"pkg"/"old.py").read_bytes(),b"before")
        self.assertFalse((self.lab/"pkg"/"new.py").exists())
    def test_recovery_is_idempotent_after_success(self):
        self.assertTrue(self.go()["verified"])
        again=self.go()
        self.assertEqual(again["state"],"FILE_RESTORE_LAB_VERIFIED")
        self.assertEqual((self.lab/"pkg"/"old.py").read_bytes(),b"before")
        self.assertFalse((self.lab/"pkg"/"new.py").exists())
    def test_missing_new_file_from_partial_rollback_is_accepted(self):
        (self.lab/"pkg"/"new.py").unlink()
        r=self.go()
        self.assertEqual(r["state"],"FILE_RESTORE_LAB_VERIFIED")

    def test_refuses_unknown_new_file(self):
        (self.lab/"pkg"/"new.py").write_bytes(b"foreign")
        self.assertEqual(self.go()["reason"],"UNRECOGNIZED_NEW_TARGET")
        self.assertEqual((self.lab/"pkg"/"old.py").read_bytes(),b"changed")
    def test_refuses_modified_snapshot(self):
        self.assertEqual(self.go(expected_sha256="f"*64)["reason"],"SNAPSHOT_DIGEST_INVALID")
    def test_failed_replace_preserves_current_content(self):
        with patch("installer.rag_p9b_file_restore_executor_lab.os.replace",
                   side_effect=OSError("INJECTED_ATOMIC_REPLACE_ERROR")):
            r=self.go()
        self.assertEqual(r["reason"],"RESTORE_EXCEPTION")
        self.assertEqual((self.lab/"pkg"/"old.py").read_bytes(),b"changed")
        self.assertEqual((self.lab/"pkg"/"new.py").read_bytes(),
                         b"P9B_LAB_INSTALLER_CREATED_V1")
        self.assertEqual(list((self.lab/"pkg").glob(".p9b-restore-*")),[])

    def test_refuses_production_root(self):
        self.assertEqual(self.go(lab_root=self.installed)["reason"],"LAB_SCOPE_INVALID")
if __name__=="__main__":unittest.main()
