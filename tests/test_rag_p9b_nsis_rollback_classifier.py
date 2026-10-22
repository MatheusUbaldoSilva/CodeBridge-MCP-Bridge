"""Read-only, deterministic NSIS rollback classification tests."""
import hashlib
from pathlib import Path
import tempfile
import unittest

from installer.rag_p9b_nsis_rollback_classifier import (
    classify_rollback_targets, main,
)
from unittest.mock import patch


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class RollbackClassificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "CodeBridge"
        self.root.mkdir()
        self.old = b"installed-original"
        self.new = b"installed-updated"
        self.first = "author_mcp/mcp_server.py"
        self.second = "rag/runtime/incremental_authorized_queue_bootstrap.py"
        self.manifest = {
            "targets": [self.first, self.second],
            "existing": {self.first: {"sha256": digest(self.old),
                                     "bytes": len(self.old)}},
        }
        self.hashes = {self.first: digest(self.new),
                       self.second: digest(b"new-only")}
        self.first_file = self.root / self.first
        self.first_file.parent.mkdir(parents=True)
        self.first_file.write_bytes(self.old)
        self.second_file = self.root / self.second

    def check(self):
        return classify_rollback_targets(self.root,self.manifest,self.hashes)

    def test_command_line_emits_plan_but_never_restores(self):
        for state,expected in (
            ("ROLLBACK_BASELINE_ALREADY_MATCHES",0),
            ("ROLLBACK_CANDIDATES_OBSERVED_ONLY",0),
            ("ROLLBACK_UNRECOGNIZED_INSTALLED_CONTENT",2),
        ):
            with self.subTest(state=state), patch(
                "installer.rag_p9b_nsis_rollback_classifier.inspect_nsis_rollback_candidates",
                return_value={"state":state,
                              "restorable":state!="ROLLBACK_UNRECOGNIZED_INSTALLED_CONTENT",
                              "changes_applied":False},
            ):
                rc=main(["--snapshot","old.zip","--installer","new.exe",
                         "--install-root",str(self.root),"--seven-zip","7z.exe"])
            self.assertEqual(rc,expected)

    def test_pristine_installation_no_rollback(self):
        report=self.check()
        self.assertEqual(report["state"],"ROLLBACK_BASELINE_ALREADY_MATCHES")
        self.assertTrue(report["restorable"])
        self.assertEqual(report["unchanged_targets"],2)
        self.assertFalse(report["changes_applied"])

    def test_expected_update_categorized_without_restoring(self):
        self.first_file.write_bytes(self.new)
        self.second_file.parent.mkdir(parents=True)
        self.second_file.write_bytes(b"new-only")
        result=self.check()
        self.assertEqual(result["state"],"ROLLBACK_CANDIDATES_OBSERVED_ONLY")
        self.assertEqual(result["restore_candidates"],1)
        self.assertEqual(result["remove_candidates"],1)
        self.assertEqual(self.first_file.read_bytes(),self.new)
        self.assertEqual(self.second_file.read_bytes(),b"new-only")
        self.assertFalse(result["changes_applied"])
        self.assertFalse(result["rollback_execution_authorized"])
        self.assertFalse(result["real_restore_rehearsed"])

    def test_unknown_modification_blocks_candidate_restore(self):
        self.first_file.write_bytes(b"operator-changed")
        result=self.check()
        self.assertEqual(result["state"],"ROLLBACK_UNRECOGNIZED_INSTALLED_CONTENT")
        self.assertFalse(result["restorable"])
        self.assertIn(self.first,result["unrecognized_targets"])

    def test_new_file_with_unknown_content_never_removed(self):
        self.second_file.parent.mkdir(parents=True)
        self.second_file.write_bytes(b"new-user-content")
        result=self.check()
        self.assertFalse(result["restorable"])
        self.assertIn(self.second,result["unrecognized_targets"])

    def test_missing_original_blocks_restore(self):
        self.first_file.unlink()
        result=self.check()
        self.assertFalse(result["restorable"])

    def test_manifest_and_hash_set_mismatch_refused(self):
        self.hashes.pop(self.second)
        self.assertFalse(self.check()["restorable"])

    def test_parent_traversal_rejected(self):
        self.manifest["targets"]=[self.first,"../outside.txt"]
        self.hashes={"../outside.txt": digest(b"test"),self.first:digest(self.new)}
        self.assertEqual(self.check()["state"],"ROLLBACK_CLASSIFICATION_BLOCKED")

    def test_file_symlink_blocked(self):
        self.second_file.parent.mkdir(parents=True)
        try:
            self.second_file.symlink_to(self.first_file)
        except OSError as exc:
            if getattr(exc, "winerror", None) == 1314:
                self.skipTest("Windows account cannot create symlinks (WinError 1314)")
            raise
        result=self.check()
        self.assertFalse(result["restorable"])
        self.assertIn(self.second,result["unrecognized_targets"])


if __name__=="__main__":
    unittest.main()
