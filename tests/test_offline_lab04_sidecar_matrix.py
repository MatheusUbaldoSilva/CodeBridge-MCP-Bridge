import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
from rag.runtime.offline_fixture_snapshot import capture_fixture, OfflineFixtureError
from rag.runtime.offline_fixture_restore import restore_fixture_snapshot, OfflineFixtureRestoreError

class Lab04SQLiteSidecarMatrix(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix="rag-lab04-sidecars-")
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)/"codebridge-rag-generation-test"
        create_bundle(self.root,[("lab","sidecars","synthetic")])

    def test_all_sqlite_sidecars_block_capture(self):
        for suffix in ("-wal","-shm","-journal"):
            with self.subTest(suffix=suffix):
                sidecar=self.root/("rag_index.sqlite3"+suffix)
                sidecar.write_bytes(b"synthetic")
                try:
                    with self.assertRaises(OfflineFixtureError):
                        capture_fixture(self.root,"reject_sidecar")
                    self.assertFalse((self.root/"offline-fixture-backups"/"reject_sidecar").exists())
                finally:
                    sidecar.unlink()

    def test_all_sqlite_sidecars_block_restoration(self):
        capture_fixture(self.root,"clean")
        payload=self.root/"offline-fixture-backups"/"clean"/"snapshot"
        for suffix in ("-wal","-shm","-journal"):
            with self.subTest(suffix=suffix):
                sidecar=payload/("rag_index.sqlite3"+suffix)
                sidecar.write_bytes(b"synthetic")
                try:
                    with self.assertRaises(OfflineFixtureRestoreError):
                        restore_fixture_snapshot(self.root,"clean","denied")
                    self.assertFalse((self.root/"offline-fixture-restores"/"denied").exists())
                finally:
                    sidecar.unlink()
        result=restore_fixture_snapshot(self.root,"clean","clean_restore")
        self.assertEqual(result["state"],"LAB_FIXTURE_RESTORED_NOT_ACTIVATED")
        self.assertFalse(result["production_authorized"])

if __name__=="__main__":
    unittest.main()
