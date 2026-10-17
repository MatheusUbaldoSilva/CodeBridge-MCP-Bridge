import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
from rag.index.manifest import ManifestError
from rag.runtime.offline_fixture_snapshot import capture_fixture
from rag.runtime.incremental_bundle_validate import (
    validate_incremental_bundle, IncrementalBundleValidationError,
)

class CrossStoreCapturedSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="rag-lab04-b-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "codebridge-rag-generation-test"
        create_bundle(self.root, [("lab","sample","synthetic data")])
        capture_fixture(self.root, "isolated")
        self.snapshot = self.root / "offline-fixture-backups" / "isolated" / "snapshot"

    def test_captured_bundle_validates_readonly(self):
        result = validate_incremental_bundle(self.snapshot)
        self.assertEqual(result["state"], "VALIDATED_OFFLINE_NOT_PUBLISHED")

    def test_manifest_tampering_is_rejected(self):
        (self.snapshot / "rag-index-manifest.json").write_text("{}", encoding="utf-8")
        with self.assertRaises((IncrementalBundleValidationError, ManifestError, ValueError, KeyError, TypeError)):
            validate_incremental_bundle(self.snapshot)

    def test_sqlite_corruption_is_rejected(self):
        (self.snapshot / "rag_index.sqlite3").write_bytes(b"not a sqlite database")
        with self.assertRaises((IncrementalBundleValidationError, sqlite3.DatabaseError)):
            validate_incremental_bundle(self.snapshot)

    def test_missing_qdrant_tree_is_rejected(self):
        shutil.rmtree(self.snapshot / "qdrant")
        with self.assertRaises(IncrementalBundleValidationError):
            validate_incremental_bundle(self.snapshot)

if __name__ == "__main__":
    unittest.main()
