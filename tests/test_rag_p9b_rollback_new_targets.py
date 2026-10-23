import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile
import json
import hashlib

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
           return_value={"verified":True})
    def test_new_target_digest_match_is_observation_not_delete_approval(self,_):
        target=self.installed/"rag"/"b.py"
        target.parent.mkdir()
        target.write_bytes(b"expected")
        digest=hashlib.sha256(b"expected").hexdigest()
        r=inspect_new_targets(self.zip,self.installed,expected_new_hashes={"rag/b.py":digest})
        self.assertEqual(r["state"],"NEW_TARGETS_CONTENT_VERIFIED")
        self.assertTrue(r["ownership_evidence_verified"])
        self.assertFalse(r["delete_authorized"])
        self.assertEqual(target.read_bytes(),b"expected")

    @patch("installer.rag_p9b_rollback_new_targets.verify_installer_rollback_snapshot",
           return_value={"verified":True})
    def test_foreign_new_target_bytes_refused(self,_):
        target=self.installed/"rag"/"b.py"
        target.parent.mkdir()
        target.write_bytes(b"foreign")
        digest=hashlib.sha256(b"expected").hexdigest()
        r=inspect_new_targets(self.zip,self.installed,expected_new_hashes={"rag/b.py":digest})
        self.assertEqual(r["reason"],"UNRECOGNIZED_NEW_TARGET_CONTENT")
        self.assertEqual(target.read_bytes(),b"foreign")

    @patch("installer.rag_p9b_rollback_new_targets.verify_installer_rollback_snapshot",
           return_value={"verified":True})
    def test_incomplete_expected_digests_refused(self,_):
        r=inspect_new_targets(self.zip,self.installed,expected_new_hashes={})
        self.assertEqual(r["reason"],"NEW_TARGET_DIGEST_SCOPE_INVALID")

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
