import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from installer.rag_p9b_artifact_pair_gate import assess_artifact_pair


class PairGateTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.installed=self.root/"installed"
        self.installed.mkdir()
        self.exe=self.root/"preview.exe"
        self.exe.write_bytes(b"synthetic installer")
        self.ehash=hashlib.sha256(self.exe.read_bytes()).hexdigest()
        self.backup=self.root/"backup.zip"
        with ZipFile(self.backup,"w") as z:
            z.writestr("manifest.json",json.dumps({"installer_sha256":self.ehash}))
        self.zhash=hashlib.sha256(self.backup.read_bytes()).hexdigest()
        self.source="a"*40

    def check(self,**kwargs):
        opts=dict(expected_installer_sha256=self.ehash,
                  expected_snapshot_sha256=self.zhash,
                  expected_source_commit=self.source)
        opts.update(kwargs)
        return assess_artifact_pair(self.exe,self.backup,self.installed,**opts)

    @patch("installer.rag_p9b_artifact_pair_gate.inspect_installer_snapshot_baseline",
           return_value={"matches":True,"files_checked":3})
    @patch("installer.rag_p9b_artifact_pair_gate.verify_installer_rollback_snapshot",
           return_value={"verified":True})
    def test_matching_only_observed(self,*_):
        r=self.check()
        self.assertTrue(r["paired"])
        self.assertFalse(r["operator_execution_authorized"])
        self.assertFalse(r["installer_executed"])

    def test_wrong_installer_hash_blocks(self):
        r=self.check(expected_installer_sha256="b"*64)
        self.assertEqual(r["reason"],"ARTIFACT_HASH_MISMATCH")

    def test_wrong_zip_hash_blocks(self):
        r=self.check(expected_snapshot_sha256="b"*64)
        self.assertEqual(r["reason"],"ARTIFACT_HASH_MISMATCH")

    def test_duplicate_manifest_keys_are_not_trusted(self):
        raw='{"installer_sha256":"'+self.ehash+'","installer_sha256":"'+self.ehash+'"}'
        with ZipFile(self.backup,"w") as z:
            z.writestr("manifest.json",raw)
        report=self.check(expected_snapshot_sha256=hashlib.sha256(
            self.backup.read_bytes()).hexdigest())
        self.assertEqual(report["reason"],"ARTIFACT_READ_UNVERIFIED")
        self.assertFalse(report["paired"])

    def test_wrong_manifest_binding_blocks(self):
        with ZipFile(self.backup,"w") as z:
            z.writestr("manifest.json",json.dumps({"installer_sha256":"b"*64}))
        r=self.check(expected_snapshot_sha256=hashlib.sha256(self.backup.read_bytes()).hexdigest())
        self.assertEqual(r["reason"],"BACKUP_INSTALLER_BINDING_MISMATCH")

    @patch("installer.rag_p9b_artifact_pair_gate.verify_installer_rollback_snapshot",
           return_value={"verified":True})
    @patch("installer.rag_p9b_artifact_pair_gate.inspect_installer_snapshot_baseline",
           return_value={"matches":False})
    def test_changed_install_blocks(self,*_):
        self.assertEqual(self.check()["reason"],"INSTALLED_BASELINE_CHANGED")

    def test_missing_source_commit_blocks(self):
        self.assertEqual(self.check(expected_source_commit="short")["reason"],
                         "ARTIFACT_IDENTITY_UNVERIFIED")


if __name__=="__main__":
    unittest.main()
