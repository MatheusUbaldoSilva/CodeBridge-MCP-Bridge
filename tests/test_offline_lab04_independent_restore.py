import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
from rag.runtime.offline_fixture_snapshot import capture_fixture
from rag.runtime.offline_fixture_restore import restore_fixture_snapshot, OfflineFixtureRestoreError
from rag.runtime.incremental_bundle_validate import validate_incremental_bundle

class Lab04IndependentRestoration(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="rag-lab04-c-")
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/"codebridge-rag-generation-test"
        create_bundle(self.root,[("alpha","one","synthetic"),("beta","two","synthetic")])
        self.pointer=self.root/"active-generation.json"
        self.pointer.write_text('{"generation":"must-not-change"}',encoding="utf-8")
        capture_fixture(self.root,"saved")

    def test_two_isolated_restores_do_not_switch_active_generation(self):
        original=hashlib.sha256(self.pointer.read_bytes()).hexdigest()
        source=self.root/"offline-fixture-backups"/"saved"/"snapshot"
        for name in ("restore_alpha","restore_beta"):
            report=restore_fixture_snapshot(self.root,"saved",name)
            self.assertEqual(report["state"],"LAB_FIXTURE_RESTORED_NOT_ACTIVATED")
            self.assertFalse(report["production_authorized"])
            restored=self.root/"offline-fixture-restores"/name/"snapshot"
            self.assertEqual(validate_incremental_bundle(restored),validate_incremental_bundle(source))
            self.assertEqual(hashlib.sha256(self.pointer.read_bytes()).hexdigest(),original)
        with self.assertRaises(OfflineFixtureRestoreError):
            restore_fixture_snapshot(self.root,"saved","restore_alpha")
        self.assertTrue((self.root/"offline-fixture-restores"/"restore_beta"/"snapshot").is_dir())
        self.assertEqual(hashlib.sha256(self.pointer.read_bytes()).hexdigest(),original)

if __name__=="__main__":
    unittest.main()
