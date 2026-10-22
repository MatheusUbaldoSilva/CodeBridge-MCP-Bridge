import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile
import json

from installer.rag_p9b_rollback_new_targets import inspect_new_targets


class TargetTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=Path(t.name)
        self.installed=self.root/"installed"
        self.installed.mkdir()
        self.zip=self.root/"backup.zip"
        with ZipFile(self.zip,"w") as z:
            z.writestr("manifest.json",json.dumps({
                "targets":["rag/a.py","rag/b.py"],"existing":{"rag/a.py":{}}}))

    @patch("installer.rag_p9b_rollback_new_targets.verify_installer_rollback_snapshot",
           return_value={"verified":True})
    def test_new_target_reported_not_deleted(self,_):
        r=inspect_new_targets(self.zip,self.installed)
        self.assertEqual(r["state"],"NEW_TARGETS_OBSERVED_ONLY")
        self.assertEqual(r["count"],1)
        self.assertFalse(r["delete_authorized"])

    @patch("installer.rag_p9b_rollback_new_targets.verify_installer_rollback_snapshot",
           return_value={"verified":False})
    def test_unverified_snapshot_fails(self,_):
        r=inspect_new_targets(self.zip,self.installed)
        self.assertEqual(r["reason"],"ROLLBACK_SNAPSHOT_INVALID")

    @patch("installer.rag_p9b_rollback_new_targets.verify_installer_rollback_snapshot",
           return_value={"verified":True})
    def test_directory_collision_fails(self,_):
        (self.installed/"rag"/"b.py").mkdir(parents=True)
        r=inspect_new_targets(self.zip,self.installed)
        self.assertEqual(r["reason"],"NEW_TARGET_NOT_REGULAR")


if __name__=="__main__":
    unittest.main()
