import tempfile
import sys
import unittest
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


if __name__=="__main__":
    unittest.main()
