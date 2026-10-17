import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
from rag.runtime.offline_fixture_snapshot import capture_fixture
from rag.runtime.offline_fixture_restore import restore_fixture_snapshot,OfflineFixtureRestoreError

class Lab04RestoreBoundaryTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix="rag-lab04-e-")
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)/"codebridge-rag-generation-test"
        create_bundle(self.root,[("alpha","one","synthetic")])
        self.pointer=self.root/"active-generation.json"
        self.pointer.write_text('{"generation":"untouched"}',encoding="utf-8")
        capture_fixture(self.root,"saved")
    def test_forged_backup_authorization_is_rejected(self):
        report=self.root/"offline-fixture-backups"/"saved"/"report.json"
        metadata=json.loads(report.read_text(encoding="utf-8"))
        metadata["production_authorized"]=True
        report.write_text(json.dumps(metadata),encoding="utf-8")
        prior=hashlib.sha256(self.pointer.read_bytes()).hexdigest()
        with self.assertRaises(OfflineFixtureRestoreError):
            restore_fixture_snapshot(self.root,"saved","rejected")
        self.assertFalse((self.root/"offline-fixture-restores"/"rejected").exists())
        self.assertEqual(hashlib.sha256(self.pointer.read_bytes()).hexdigest(),prior)
    def test_existing_destination_and_unsafe_name_rejected(self):
        restore_fixture_snapshot(self.root,"saved","good")
        prior=(self.root/"offline-fixture-restores"/"good"/"snapshot"/"rag_index.sqlite3")
        before=hashlib.sha256(prior.read_bytes()).hexdigest()
        with self.assertRaises(OfflineFixtureRestoreError):
            restore_fixture_snapshot(self.root,"saved","good")
        with self.assertRaises(OfflineFixtureRestoreError):
            restore_fixture_snapshot(self.root,"saved","../outside")
        self.assertEqual(hashlib.sha256(prior.read_bytes()).hexdigest(),before)
        self.assertFalse((self.root/"active-generation.json").read_text(encoding="utf-8") != '{"generation":"untouched"}')

if __name__=="__main__":
    unittest.main()
