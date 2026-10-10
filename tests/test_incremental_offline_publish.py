"""Offline publish rollback tests: never address production RAG paths."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_incremental_bundle_validate import fixture
from rag.runtime.incremental_offline_publish import (
    rehearsal_publish, OfflinePublishError,
)
from rag.runtime.incremental_bundle_validate import validate_incremental_bundle


class OfflinePublicationTests(unittest.TestCase):
    def test_backup_and_activate(self):
        with tempfile.TemporaryDirectory() as tmp:
            test_root = Path(tmp) / "codebridge-rag-offline-test"
            test_root.mkdir()
            source, active = test_root / "candidate", test_root / "active"
            source.mkdir()
            fixture(source)
            shutil.copytree(source, active)
            result = rehearsal_publish(source, active)
            self.assertEqual(result["state"], "OFFLINE_TEST_ACTIVATED")
            self.assertEqual(validate_incremental_bundle(active)["documents"], 1)
            self.assertTrue((test_root / "active.rollback").is_dir())

    def test_failure_restores_active(self):
        for point in ("copy", "backup", "activate"):
            with self.subTest(point=point):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp) / "codebridge-rag-offline-test"
                    root.mkdir()
                    candidate, active = root / "candidate", root / "active"
                    candidate.mkdir()
                    fixture(candidate)
                    shutil.copytree(candidate, active)
                    with self.assertRaises(OfflinePublishError):
                        rehearsal_publish(candidate, active, fail_after=point)
                    self.assertEqual(validate_incremental_bundle(active)["documents"], 1)
                    self.assertFalse((root / "active.incoming").exists())

    def test_refuses_non_test_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(OfflinePublishError):
                rehearsal_publish(Path(tmp)/"candidate", Path(tmp)/"active")


if __name__ == "__main__":
    unittest.main()
