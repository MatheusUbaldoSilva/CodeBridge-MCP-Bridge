import tempfile
import sys
import unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
from rag.runtime.generation_verified_backup import (
    backup_generation, verify_generation_backup, VerifiedBackupError)


class VerifiedGenerationBackupTests(unittest.TestCase):
    def test_backup_validation_tamper_detection_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"codebridge-rag-generation-test"
            source=root/"generations"/"one"
            source.parent.mkdir(parents=True)
            create_bundle(source,[("a","manual","original")])
            result=backup_generation(root,"one","before_update")
            self.assertEqual(result["state"],"VERIFIED_TEST_BACKUP")
            self.assertEqual(result["report"]["documents"],1)
            self.assertEqual(verify_generation_backup(root,"before_update")["chunks"],1)
            with self.assertRaises(VerifiedBackupError):
                backup_generation(root,"one","before_update")
            (root/"backups"/"before_update"/"rag-index-manifest.json").write_text("tampered")
            with self.assertRaisesRegex(VerifiedBackupError,"hash mismatch"):
                verify_generation_backup(root,"before_update")

    def test_refuses_non_test_root_and_missing_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(VerifiedBackupError):
                backup_generation(Path(tmp),"one","backup")
            root=Path(tmp)/"codebridge-rag-generation-test"
            root.mkdir()
            with self.assertRaises(VerifiedBackupError):
                backup_generation(root,"missing","backup")


    def test_existing_checksum_manifest_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "codebridge-rag-generation-test"
            generation = root / "generations" / "one"
            generation.parent.mkdir(parents=True)
            create_bundle(generation, [("a", "doc", "original")])
            backups = root / "backups"
            backups.mkdir()
            digest_path = backups / "reserved.sha256.json"
            digest_path.write_text("DO_NOT_OVERWRITE", encoding="utf-8")
            with self.assertRaisesRegex(VerifiedBackupError, "never overwrite"):
                backup_generation(root, "one", "reserved")
            self.assertEqual(
                digest_path.read_text(encoding="utf-8"), "DO_NOT_OVERWRITE")
            self.assertFalse((backups / "reserved").exists())

    def test_symlinked_backup_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "codebridge-rag-generation-test"
            generation = root / "generations" / "one"
            generation.parent.mkdir(parents=True)
            create_bundle(generation, [("a", "doc", "original")])
            backup_generation(root, "one", "safe")
            forbidden = root / "backups"
            real_is_symlink = Path.is_symlink
            with patch.object(
                Path, "is_symlink", autospec=True,
                side_effect=lambda path:
                    path == forbidden or real_is_symlink(path)):
                with self.assertRaisesRegex(VerifiedBackupError, "symlink"):
                    backup_generation(root, "one", "another")
                with self.assertRaisesRegex(VerifiedBackupError, "symlink"):
                    verify_generation_backup(root, "safe")
            self.assertFalse((root / "backups" / "another").exists())
            self.assertTrue((root / "backups" / "safe").is_dir())

if __name__=="__main__":
    unittest.main()
