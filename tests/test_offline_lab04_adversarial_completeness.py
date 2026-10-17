import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
from rag.runtime.offline_fixture_snapshot import capture_fixture
from rag.runtime.offline_fixture_restore import restore_fixture_snapshot,OfflineFixtureRestoreError

class Lab04AdversarialCompletenessTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="rag-lab04-adversarial-")
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/"codebridge-rag-generation-test"
        create_bundle(self.root,[("lab","adversarial","synthetic")])
        capture_fixture(self.root,"saved")
        self.backup=self.root/"offline-fixture-backups"/"saved"

    def test_unexpected_file_in_snapshot_blocks_restore(self):
        extra=self.backup/"snapshot"/"unexpected-extra.bin"
        extra.write_bytes(b"not-in-report")
        with self.assertRaises(OfflineFixtureRestoreError):
            restore_fixture_snapshot(self.root,"saved","extra_denied")
        self.assertFalse((self.root/"offline-fixture-restores"/"extra_denied").exists())

    def test_missing_manifest_digest_blocks_restore(self):
        report=self.backup/"report.json"
        data=json.loads(report.read_text(encoding="utf-8"))
        data["hashes"].pop("rag-index-manifest.json")
        report.write_text(json.dumps(data),encoding="utf-8")
        with self.assertRaises(OfflineFixtureRestoreError):
            restore_fixture_snapshot(self.root,"saved","hash_denied")
        self.assertFalse((self.root/"offline-fixture-restores"/"hash_denied").exists())

if __name__=="__main__":
    unittest.main()
