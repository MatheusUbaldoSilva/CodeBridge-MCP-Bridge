import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
from rag.runtime.offline_fixture_snapshot import capture_fixture,OfflineFixtureError

class LabIndependentCaptureTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix="rag-lab04-a-")
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)/"codebridge-rag-generation-test"
        create_bundle(self.root,[("lab","capture","synthetic")])
    def test_two_distinct_snapshots_are_isolated_and_source_unchanged(self):
        sources=[p for p in self.root.rglob("*") if p.is_file()]
        before={p.relative_to(self.root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
        a=capture_fixture(self.root,"capture_alpha")
        b=capture_fixture(self.root,"capture_beta")
        self.assertEqual(a["state"],"LAB_FIXTURE_SNAPSHOT_ONLY")
        self.assertEqual(b["state"],"LAB_FIXTURE_SNAPSHOT_ONLY")
        self.assertTrue((self.root/"offline-fixture-backups"/"capture_alpha").is_dir())
        self.assertTrue((self.root/"offline-fixture-backups"/"capture_beta").is_dir())
        for source,sha in before.items():
            self.assertEqual(hashlib.sha256((self.root/source).read_bytes()).hexdigest(),sha)
        with self.assertRaises(OfflineFixtureError):
            capture_fixture(self.root,"capture_alpha")
        self.assertFalse(a["production_authorized"])
        self.assertFalse(b["production_authorized"])

if __name__=="__main__":
    unittest.main()
